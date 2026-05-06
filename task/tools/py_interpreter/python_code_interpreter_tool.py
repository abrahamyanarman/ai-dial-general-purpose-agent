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
        #TODO:
        # 1. Set dial_endpoint
        # 2. Set mcp_client
        # 3. Set _code_execute_tool: Optional[MCPToolModel] as None at start, then iterate through `mcp_tool_models` and
        #    if any of tool model has the same same as `tool_name` then set _code_execute_tool as tool model
        # 4. If `_code_execute_tool` is null then raise error (We cannot set up PythonCodeInterpreterTool without tool that executes code)
        self.dial_endpoint = dial_endpoint
        self.mcp_client = mcp_client
        self._code_execute_tool: Optional[MCPToolModel] = None
        for model in mcp_tool_models:
            if model.name == tool_name:
                self._code_execute_tool = model
                break
        
        if self._code_execute_tool is None:
            raise ValueError(f"Code execution tool '{tool_name}' not found in MCP models")

    @classmethod
    async def create(
            cls,
            mcp_url: str,
            tool_name: str,
            dial_endpoint: str,
    ) -> 'PythonCodeInterpreterTool':
        """Async factory method to create PythonCodeInterpreterTool"""
        #TODO:
        # 1. Create MCPClient
        # 2. Get tools
        # 3. Create PythonCodeInterpreterTool instance and return it
        mcp_client = await MCPClient.create(mcp_url)
        tools = await mcp_client.get_tools()
        return cls(mcp_client, tools, tool_name, dial_endpoint)

    @property
    def show_in_stage(self) -> bool:
        # TODO: set as False since we will have custom variant of representation in Stage
        return False

    @property
    def name(self) -> str:
        # TODO: provide `_code_execute_tool` name
        return self._code_execute_tool.name

    @property
    def description(self) -> str:
        # TODO: provide `_code_execute_tool` description
        return self._code_execute_tool.description

    @property
    def parameters(self) -> dict[str, Any]:
        # TODO: provide `_code_execute_tool` parameters
        return self._code_execute_tool.parameters

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. Load arguments with `json`
        # 2. Get `code` from arguments
        # 3. Get `session_id` from arguments (it is optional parameter, use get method)
        # 4. Get stage from `tool_call_params`
        # 5. Append content to stage: "## Request arguments: \n"
        # 6. Append content to stage: `"```python\n\r{code}\n\r```\n\r"` it will show code in stage as python markdown
        # 7. Append session to stage:
        #       - if `session_id` is present and not 0 then append to stage `f"**session_id**: {session_id}\n\r"`
        #       - otherwise append "New session will be created\n\r"
        # 8. Make tool call
        # 9. Load retrieved response as json (️⚠️ here can be potential issues if you didn't properly implemented
        #    MCPClient tool call, it must return string)
        # 10. Validate result with _ExecutionResult (it is full copy of https://github.com/khshanovskyi/mcp-python-code-interpreter/blob/main/interpreter/models.py)
        # 11. If execution_result contains files we need to pool files from PyInterpreter and upload them to DIAL bucked:
        #       - Create Dial client
        #       - Get with client `my_appdata_home` path as `files_home`
        #       - Iterated through files and:
        #           - get file name and mime_type and assign to appropriate variables
        #           - get resource with mcp client by URL from file (https://github.com/khshanovskyi/mcp-python-code-interpreter/blob/main/interpreter/server.py#L429)
        #           - according to MCP binary resources must be encoded with base64 https://modelcontextprotocol.io/specification/2025-06-18/server/resources#binary-content
        #             Check if mime_type starts with `text/` or some of 'application/json', 'application/xml', is yes
        #             then encode resource with 'utf-8' format (text will be present as bytes to upload to DIAL bucket).
        #             Otherwise (binary file) decode it with `b64decode`
        #           - Prepare URL to upload downloaded file: f"files/{(files_home / file_name).as_posix()}"
        #           - Upload file with DIAL client
        #           - Prepare Attachment with url, type (mime_type), and title (file_name)
        #           - Add attachment to stage and also add this attachment to choice (it will be chown in both stage and choice)
        #       - Add to execution_result json addition
        # 12. Check if execution_result output present and if yes iterate through all output results and cut it length
        #     to 1000 chars, it is needed to avoid high costs and context window overload
        # 13. Append to stage response f"```json\n\r{execution_result.model_dump_json(indent=2)}\n\r```\n\r"
        # 14. Return execution result as string (model_dump_json method)
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        code = arguments.get("code", "")
        session_id = arguments.get("session_id")
        
        stage = tool_call_params.stage
        stage.append_content("## Request arguments: \n")
        stage.append_content(f"```python\n\r{code}\n\r```\n\r")
        
        if session_id and session_id != 0:
            stage.append_content(f"**session_id**: {session_id}\n\r")
        else:
            stage.append_content("New session will be created\n\r")
            
        mcp_response = await self.mcp_client.call_tool(self.name, arguments)
        execution_result_dict = json.loads(mcp_response)
        execution_result = _ExecutionResult.validate(execution_result_dict)
        
        if execution_result.files:
            dial_client = Dial(base_url=self.dial_endpoint, api_key=tool_call_params.api_key)
            files_home = dial_client.files.my_appdata_home()
            
            for file_info in execution_result.files:
                file_name = file_info.name
                mime_type = file_info.mime_type
                
                resource_content = await self.mcp_client.get_resource(AnyUrl(file_info.url))
                
                if mime_type.startswith("text/") or mime_type in ['application/json', 'application/xml']:
                    file_bytes = resource_content.encode("utf-8") if isinstance(resource_content, str) else resource_content
                else:
                    file_bytes = base64.b64decode(resource_content) if isinstance(resource_content, str) else resource_content
                    
                upload_url = f"files/{(files_home / file_name).as_posix()}"
                uploaded_file = dial_client.files.upload(upload_url, file_bytes, mime_type)
                
                attachment = Attachment(url=uploaded_file.url, type=mime_type, title=file_name)
                stage.append_attachment(attachment)
                tool_call_params.choice.append_attachment(attachment)

        if execution_result.outputs:
            for out in execution_result.outputs:
                if out.text and len(out.text) > 1000:
                    out.text = out.text[:1000] + "... [truncated]"
        
        stage.append_content(f"```json\n\r{execution_result.model_dump_json(indent=2)}\n\r```\n\r")
        return execution_result.model_dump_json()
