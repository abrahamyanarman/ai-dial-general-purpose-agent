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
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def connect(self):
        """Connect to MCP server"""
        if self.session is not None:
            return

        self._streams_context = streamablehttp_client(self.server_url)
        read_stream, write_stream, _ = await self._streams_context.__aenter__()

        self._session_context = ClientSession(read_stream, write_stream)
        self.session = await self._session_context.__aenter__()

        init_result = await self.session.initialize()
        print(f"[MCPClient] Initialized session for {self.server_url}: {init_result}")

    async def get_tools(self) -> list[MCPToolModel]:
        """Get available tools from MCP server"""
        tools_result = await self.session.list_tools()
        tools: list[MCPToolModel] = []
        for tool in tools_result.tools:
            tools.append(
                MCPToolModel(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {"type": "object", "properties": {}},
                )
            )
        return tools

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        result: CallToolResult = await self.session.call_tool(tool_name, tool_args)

        text_parts: list[str] = []
        for content_item in result.content:
            if isinstance(content_item, TextContent):
                text_parts.append(content_item.text)
            else:
                text_parts.append(str(content_item))

        return "\n".join(text_parts)

    async def get_resource(self, uri: AnyUrl) -> str | bytes:
        """Get specific resource content"""
        resource_result: ReadResourceResult = await self.session.read_resource(uri)
        for content_item in resource_result.contents:
            if isinstance(content_item, TextResourceContents):
                return content_item.text
            if isinstance(content_item, BlobResourceContents):
                return content_item.blob
        return ""

    async def close(self):
        """Close connection to MCP server"""
        try:
            if self._session_context is not None:
                await self._session_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"⚠️ Error closing MCP session: {e}")

        try:
            if self._streams_context is not None:
                await self._streams_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"⚠️ Error closing MCP streams: {e}")

        self.session = None
        self._session_context = None
        self._streams_context = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False
