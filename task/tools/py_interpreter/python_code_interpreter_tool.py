import base64
import json
from typing import Any, Optional

from aidial_client import Dial
from aidial_sdk.chat_completion import Message, Attachment
from pydantic import StrictStr, AnyUrl

from task.tools.base import BaseTool
from task.tools.py_interpreter._response import _ExecutionResult
from task.tools.mcp.mcp_client import MCPClient
from task.tools.mcp.mcp_tool_model import MCPToolModel
from task.tools.models import ToolCallParams


_TEXT_MIME_TYPES = {"application/json", "application/xml"}


class PythonCodeInterpreterTool(BaseTool):
    """
    Uses https://github.com/khshanovskyi/mcp-python-code-interpreter PyInterpreter MCP Server.

    ⚠️ Pay attention that this tool will wrap all the work with PyInterpreter MCP Server.
    """

    def __init__(
            self,
            mcp_client: MCPClient,
            mcp_tool_models: list[MCPToolModel],
            tool_name: str,
            dial_endpoint: str,
    ):
        """
        :param tool_name: it must be actual name of tool that executes code. It is 'execute_code'.
            https://github.com/khshanovskyi/mcp-python-code-interpreter/blob/main/interpreter/server.py#L303
        """
        self.dial_endpoint = dial_endpoint
        self.mcp_client = mcp_client

        self._code_execute_tool: Optional[MCPToolModel] = None
        for tool_model in mcp_tool_models:
            if tool_model.name == tool_name:
                self._code_execute_tool = tool_model
                break

        if self._code_execute_tool is None:
            raise ValueError(
                f"PythonCodeInterpreterTool cannot be set up. MCP tool with name '{tool_name}' was not found."
            )

    @classmethod
    async def create(
            cls,
            mcp_url: str,
            tool_name: str,
            dial_endpoint: str,
    ) -> 'PythonCodeInterpreterTool':
        """Async factory method to create PythonCodeInterpreterTool"""
        mcp_client = await MCPClient.create(mcp_url)
        tool_models = await mcp_client.get_tools()
        return cls(
            mcp_client=mcp_client,
            mcp_tool_models=tool_models,
            tool_name=tool_name,
            dial_endpoint=dial_endpoint,
        )

    @property
    def show_in_stage(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return self._code_execute_tool.name

    @property
    def description(self) -> str:
        return self._code_execute_tool.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._code_execute_tool.parameters

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        code = arguments["code"]
        session_id = arguments.get("session_id")

        stage = tool_call_params.stage

        stage.append_content("## Request arguments: \n")
        stage.append_content(f"```python\n\r{code}\n\r```\n\r")

        if session_id and session_id != 0:
            stage.append_content(f"**session_id**: {session_id}\n\r")
        else:
            stage.append_content("New session will be created\n\r")

        raw_response = await self.mcp_client.call_tool(self.name, arguments)

        try:
            parsed_response = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        except json.JSONDecodeError as e:
            stage.append_content(f"\n**Error**: Failed to parse interpreter response: {e}\n")
            return f"Error parsing PyInterpreter response: {e}\nRaw: {raw_response}"

        execution_result = _ExecutionResult.model_validate(parsed_response)

        if execution_result.files:
            dial_client = Dial(
                base_url=self.dial_endpoint,
                api_key=tool_call_params.api_key,
                api_version="2025-01-01-preview",
            )
            files_home = dial_client.my_appdata_home()

            for file in execution_result.files:
                file_name = file.name
                mime_type = file.mime_type

                resource = await self.mcp_client.get_resource(AnyUrl(file.uri))

                if mime_type.startswith("text/") or mime_type in _TEXT_MIME_TYPES:
                    if isinstance(resource, str):
                        file_bytes = resource.encode("utf-8")
                    else:
                        file_bytes = resource
                else:
                    if isinstance(resource, str):
                        file_bytes = base64.b64decode(resource)
                    else:
                        file_bytes = resource

                upload_url = f"files/{(files_home / file_name).as_posix()}"
                upload_result = dial_client.files.upload(
                    file_path=upload_url,
                    file=file_bytes,
                    content_type=mime_type,
                )

                attachment_url = getattr(upload_result, "url", None) or upload_url

                attachment = Attachment(
                    url=attachment_url,
                    type=mime_type,
                    title=file_name,
                )

                try:
                    stage.add_attachment(
                        type=mime_type,
                        title=file_name,
                        url=attachment_url,
                    )
                except Exception as e:
                    print(f"⚠️ Unable to attach file to stage: {e}")

                tool_call_params.choice.add_attachment(
                    type=mime_type,
                    title=file_name,
                    url=attachment_url,
                )

        if execution_result.output:
            execution_result.output = [
                (item if len(item) <= 1000 else item[:1000] + "\n... [truncated]")
                for item in execution_result.output
            ]

        stage.append_content(f"```json\n\r{execution_result.model_dump_json(indent=2)}\n\r```\n\r")

        return execution_result.model_dump_json()
