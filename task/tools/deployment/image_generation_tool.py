from typing import Any

from aidial_sdk.chat_completion import Message
from pydantic import StrictStr

from task.tools.deployment.base import DeploymentTool
from task.tools.models import ToolCallParams


class ImageGenerationTool(DeploymentTool):

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        result = await super()._execute(tool_call_params)

        if isinstance(result, Message) and result.custom_content and result.custom_content.attachments:
            choice = tool_call_params.choice
            content_parts = []
            for attachment in result.custom_content.attachments:
                attachment_type = getattr(attachment, "type", None) or ""
                if attachment_type in ("image/png", "image/jpeg") and getattr(attachment, "url", None):
                    content_parts.append(f"\n\r![image]({attachment.url})\n\r")
            for part in content_parts:
                choice.append_content(part)

            if not result.content:
                result.content = StrictStr(
                    "The image has been successfully generated according to request and shown to user!"
                )

        return result

    @property
    def deployment_name(self) -> str:
        return "dall-e-3"

    @property
    def name(self) -> str:
        return "image_generation_tool"

    @property
    def description(self) -> str:
        return (
            "Generates an image from a natural-language description using DALL-E-3. "
            "Use this tool whenever the user asks for a picture, illustration, drawing, logo, photo, scene, "
            "or any other visual artifact, including when an image must be derived from prior tool results "
            "(e.g. produce a picture that represents the current weather). "
            "Provide a vivid, self-contained `prompt` describing subject, style, mood, lighting, composition, "
            "and any required details. Optional parameters: `size` (1024x1024 / 1024x1792 / 1792x1024), "
            "`quality` (standard / hd), `style` (vivid / natural). Generated images are shown directly to the user."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Extensive description of the image that should be generated.",
                },
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1024x1792", "1792x1024"],
                    "description": "Resolution of the generated image. Defaults to 1024x1024.",
                },
                "quality": {
                    "type": "string",
                    "enum": ["standard", "hd"],
                    "description": "Quality of the generated image. `hd` produces more detail but costs more.",
                },
                "style": {
                    "type": "string",
                    "enum": ["vivid", "natural"],
                    "description": "Style of the generated image. `vivid` is hyper-real, `natural` is more muted.",
                },
            },
            "required": ["prompt"],
        }
