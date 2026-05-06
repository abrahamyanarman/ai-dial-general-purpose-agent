import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from aidial_client import AsyncDial
from aidial_sdk.chat_completion import Message, Role, CustomContent
from pydantic import StrictStr

from task.tools.base import BaseTool
from task.tools.models import ToolCallParams


class DeploymentTool(BaseTool, ABC):

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    @property
    @abstractmethod
    def deployment_name(self) -> str:
        pass

    @property
    def tool_parameters(self) -> dict[str, Any]:
        return {}

    @property
    def system_prompt(self) -> Optional[str]:
        return None

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        prompt = arguments.get("prompt", "")
        if "prompt" in arguments:
            del arguments["prompt"]

        stage = tool_call_params.stage

        client = AsyncDial(
            base_url=self.endpoint,
            api_key=tool_call_params.api_key,
            api_version="2025-01-01-preview",
        )

        messages: list[dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": Role.SYSTEM.value, "content": self.system_prompt})
        messages.append({"role": Role.USER.value, "content": prompt})

        stage.append_content("## Request arguments: \n")
        stage.append_content(f"```json\n\r{json.dumps({'prompt': prompt, **arguments}, indent=2)}\n\r```\n\r")
        stage.append_content("## Response: \n")

        create_kwargs: dict[str, Any] = {
            "messages": messages,
            "deployment_name": self.deployment_name,
            "stream": True,
            **self.tool_parameters,
        }
        if arguments:
            create_kwargs["custom_fields"] = {"configuration": arguments}

        chunks_stream = await client.chat.completions.create(**create_kwargs)

        content = ""
        attachments_collected = []
        async for chunk in chunks_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue
            if delta.content:
                content += delta.content
                stage.append_content(delta.content)
            custom_content = getattr(delta, "custom_content", None)
            if custom_content:
                attachments = getattr(custom_content, "attachments", None) or []
                for attachment in attachments:
                    attachments_collected.append(attachment)
                    try:
                        stage.add_attachment(
                            type=getattr(attachment, "type", None),
                            title=getattr(attachment, "title", None),
                            url=getattr(attachment, "url", None),
                            data=getattr(attachment, "data", None),
                            reference_url=getattr(attachment, "reference_url", None),
                            reference_type=getattr(attachment, "reference_type", None),
                        )
                    except Exception as e:
                        print(f"⚠️ Unable to add attachment to stage: {e}")

        custom_content_obj = None
        if attachments_collected:
            custom_content_obj = CustomContent(attachments=attachments_collected)

        return Message(
            role=Role.TOOL,
            content=StrictStr(content) if content else StrictStr(""),
            custom_content=custom_content_obj,
            tool_call_id=StrictStr(tool_call_params.tool_call.id),
            name=StrictStr(tool_call_params.tool_call.function.name),
        )
