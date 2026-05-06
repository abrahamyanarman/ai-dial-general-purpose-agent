import json
from abc import ABC, abstractmethod
from typing import Any

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

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. Load arguments with `json`
        # 2. Get `prompt` from arguments (by default we provide `prompt` for each deployment tool, use this param name as standard)
        # 3. Delete `prompt` from `arguments` (there can be provided additional parameters and `prompt` will be added
        #    as user message content and other parameters as `custom_fields`)
        # 4. Create AsyncDial client (api_version is 2025-01-01-preview)
        # 5. Call chat completions with:
        #   - messages (here will be just user message. Optionally, in this class you can add system prompt `property`
        #     and if any deployment tool provides system prompt then we need to set it as first message (system prompt))
        #   - stream it
        #   - deployment_name
        #   - extra_body with `custom_fields` https://dialx.ai/dial_api#operation/sendChatCompletionRequest (last request param in documentation)
        #   - **self.tool_parameters (will load all tool parameters that were set up in deployment tools as params, like
        #     `top_p`, `temperature`, etc...)
        # 6. Collect content and it to stage, also, collect custom_content -> attachments and if they are present add
        #    them to stage as attachment as well
        # 7. Return Message with tool role, content, custom_content and tool_call_id
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        prompt = arguments.get("prompt", "")
        if "prompt" in arguments:
            del arguments["prompt"]
            
        client = AsyncDial(base_url=self.endpoint, api_key=tool_call_params.api_key, api_version='2025-01-01-preview')
        
        messages = [{"role": Role.USER.value, "content": prompt}]
        
        chunks = await client.chat.completions.create(
            messages=messages,
            model=self.deployment_name,
            stream=True,
            extra_body={"custom_fields": arguments},
            **self.tool_parameters
        )
        
        collected_content = ""
        attachments = []
        
        async for chunk in chunks:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    collected_content += delta.content
                    tool_call_params.stage.append_content(delta.content)
                
                if delta.custom_content and delta.custom_content.attachments:
                    for attachment in delta.custom_content.attachments:
                        attachments.append(attachment)
                        tool_call_params.stage.append_attachment(attachment)

        return Message(
            role=Role.TOOL,
            content=collected_content,
            custom_content=CustomContent(attachments=attachments) if attachments else None,
            tool_call_id=StrictStr(tool_call_params.tool_call.id),
            name=StrictStr(self.name)
        )
