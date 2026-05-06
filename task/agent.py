import asyncio
import json
from typing import Any

from aidial_client import AsyncDial
from aidial_client.types.chat.legacy.chat_completion import CustomContent, ToolCall
from aidial_sdk.chat_completion import Message, Role, Choice, Request, Response

from task.tools.base import BaseTool
from task.tools.models import ToolCallParams
from task.utils.constants import TOOL_CALL_HISTORY_KEY
from task.utils.history import unpack_messages
from task.utils.stage import StageProcessor


class GeneralPurposeAgent:

    def __init__(
            self,
            endpoint: str,
            system_prompt: str,
            tools: list[BaseTool],
    ):
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.tools = tools
        self._tools_dict: dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self.state: dict[str, Any] = {TOOL_CALL_HISTORY_KEY: []}

    async def handle_request(self, deployment_name: str, choice: Choice, request: Request, response: Response) -> Message:
        api_key = request.api_key
        api_version = getattr(request, "api_version", None) or "2025-01-01-preview"

        client = AsyncDial(base_url=self.endpoint, api_key=api_key, api_version=api_version)

        messages = self._prepare_messages(request.messages)

        chunks = await client.chat.completions.create(
            messages=messages,
            tools=[tool.schema for tool in self.tools],
            deployment_name=deployment_name,
            stream=True,
        )

        tool_call_index_map: dict[int, Any] = {}
        content = ""

        async for chunk in chunks:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue

            if delta.content:
                choice.append_content(delta.content)
                content += delta.content

            if getattr(delta, "tool_calls", None):
                for tool_call_delta in delta.tool_calls:
                    if getattr(tool_call_delta, "id", None):
                        tool_call_index_map[tool_call_delta.index] = tool_call_delta
                    else:
                        existing = tool_call_index_map.get(tool_call_delta.index)
                        if existing is None:
                            continue
                        if getattr(tool_call_delta, "function", None):
                            argument_chunk = getattr(tool_call_delta.function, "arguments", "") or ""
                            if existing.function is None:
                                existing.function = tool_call_delta.function
                            else:
                                existing.function.arguments = (existing.function.arguments or "") + argument_chunk

        tool_calls_list = [
            ToolCall.validate(tc.dict(exclude_none=True) if hasattr(tc, "dict") else tc)
            for tc in tool_call_index_map.values()
        ]

        assistant_message = Message(
            role=Role.ASSISTANT,
            content=content if content else None,
            tool_calls=tool_calls_list if tool_calls_list else None,
        )

        if assistant_message.tool_calls:
            api_key_value = api_key.api_key if hasattr(api_key, "api_key") else api_key
            conversation_id = request.headers.get("x-conversation-id", "") if request.headers else ""

            tasks = [
                self._process_tool_call(tc, choice, api_key_value, conversation_id)
                for tc in assistant_message.tool_calls
            ]
            tool_messages = await asyncio.gather(*tasks)

            self.state[TOOL_CALL_HISTORY_KEY].append(assistant_message.dict(exclude_none=True))
            self.state[TOOL_CALL_HISTORY_KEY].extend(tool_messages)

            return await self.handle_request(deployment_name, choice, request, response)

        choice.set_state(self.state)
        return assistant_message

    def _prepare_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        unpacked = unpack_messages(messages, self.state.get(TOOL_CALL_HISTORY_KEY, []))
        unpacked.insert(0, {"role": Role.SYSTEM.value, "content": self.system_prompt})

        print("\n=== Conversation history ===")
        for msg in unpacked:
            try:
                print(json.dumps(msg, indent=2, default=str))
            except Exception as e:
                print(f"<unserializable message: {e}>")
        print("=== End history ===\n")

        return unpacked

    async def _process_tool_call(self, tool_call: ToolCall, choice: Choice, api_key: str, conversation_id: str) -> dict[str, Any]:
        tool_name = tool_call.function.name
        stage = StageProcessor.open_stage(choice, name=f"Tool call: {tool_name}")
        try:
            tool = self._tools_dict.get(tool_name)
            if tool is None:
                stage.append_content(f"⚠️ Tool '{tool_name}' is not registered.")
                error_msg = Message(
                    role=Role.TOOL,
                    name=tool_name,
                    tool_call_id=tool_call.id,
                    content=f"Error: tool '{tool_name}' is not available.",
                )
                return error_msg.dict(exclude_none=True)

            if tool.show_in_stage:
                stage.append_content("## Request arguments: \n")
                try:
                    parsed_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    parsed_args = {"raw": tool_call.function.arguments}
                stage.append_content(
                    f"```json\n\r{json.dumps(parsed_args, indent=2)}\n\r```\n\r"
                )
                stage.append_content("## Response: \n")

            tool_call_params = ToolCallParams(
                tool_call=tool_call,
                stage=stage,
                choice=choice,
                api_key=api_key,
                conversation_id=conversation_id,
            )
            tool_message = await tool.execute(tool_call_params)

            return tool_message.dict(exclude_none=True)
        finally:
            StageProcessor.close_stage_safely(stage)
