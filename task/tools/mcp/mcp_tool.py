import json
from typing import Any

from aidial_sdk.chat_completion import Message

from task.tools.base import BaseTool
from task.tools.mcp.mcp_client import MCPClient
from task.tools.mcp.mcp_tool_model import MCPToolModel
from task.tools.models import ToolCallParams


class MCPTool(BaseTool):

    def __init__(self, client: MCPClient, mcp_tool_model: MCPToolModel):
        #TODO:
        # 1. Set client
        # 2. Set mcp_tool_model
        raise NotImplementedError()

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. Load arguments wit `json`
        # 2. Get content with mcp client tool call
        # 3. Append retrieved content to stage
        # 4. return content
        raise NotImplementedError()

    @property
    def name(self) -> str:
        # TODO: provide name from mcp_tool_model
        raise NotImplementedError()

    @property
    def description(self) -> str:
        # TODO: provide description from mcp_tool_model
        raise NotImplementedError()

    @property
    def parameters(self) -> dict[str, Any]:
        # TODO: provide parameters from mcp_tool_model
        raise NotImplementedError()
