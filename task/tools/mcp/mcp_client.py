from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent, ReadResourceResult, TextResourceContents, BlobResourceContents
from pydantic import AnyUrl

from task.tools.mcp.mcp_tool_model import MCPToolModel


class MCPClient:
    """Handles MCP server connection and tool execution"""

    def __init__(self, mcp_server_url: str) -> None:
        self.server_url = mcp_server_url
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None

    @classmethod
    async def create(cls, mcp_server_url: str) -> 'MCPClient':
        """Async factory method to create and connect MCPClient"""
        #TODO:
        # 1. Create instance of MCPClient with `cls`
        # 2. Connect to MCP server
        # 3. return created instance
        raise NotImplementedError()

    async def connect(self):
        """Connect to MCP server"""
        #TODO:
        # 1. Check if session is present, if yes just return to finsh execution
        # 2. Call `streamablehttp_client` method with `server_url` and set as `self._streams_context`
        # 3. Enter `self._streams_context`, result set as `read_stream, write_stream, _`
        # 4. Create ClientSession with streams from above and set as `self._session_context`
        # 5. Enter `self._session_context` and set as self.session
        # 6. Initialize session and print its result to console
        raise NotImplementedError()


    async def get_tools(self) -> list[MCPToolModel]:
        """Get available tools from MCP server"""
        #TODO: Get and return MCP tools as list of MCPToolModel
        raise NotImplementedError()

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        #TODO: Make tool call and return its result. Do it in proper way (it returns array of content and you need to handle it properly)
        raise NotImplementedError()

    async def get_resource(self, uri: AnyUrl) -> str | bytes:
        """Get specific resource content"""
        #TODO: Get and return resource. Resources can be returned as TextResourceContents and BlobResourceContents, you
        #      need to return resource value (text or blob)
        raise NotImplementedError()

    async def close(self):
        """Close connection to MCP server"""
        #TODO:
        # 1. Close `self._session_context`
        # 2. Close `self._streams_context`
        # 3. Set session, _session_context and _streams_context as None
        raise NotImplementedError()

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False

