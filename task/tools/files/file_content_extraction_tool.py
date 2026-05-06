import json
from typing import Any

from aidial_sdk.chat_completion import Message

from task.tools.base import BaseTool
from task.tools.models import ToolCallParams
from task.utils.dial_file_conent_extractor import DialFileContentExtractor


class FileContentExtractionTool(BaseTool):
    """
    Extracts text content from files. Supported: PDF (text only), TXT, CSV (as markdown table), HTML/HTM.
    PAGINATION: Files >10,000 chars are paginated. Response format: `**Page #X. Total pages: Y**` appears at end if paginated.
    USAGE: Start with page=1 (by default)
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    @property
    def show_in_stage(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "file_content_extraction_tool"

    @property
    def description(self) -> str:
        return (
            "Extracts text content from files attached by the user. "
            "Supported formats: PDF (text-only, no images/scans), TXT, CSV (returned as a markdown table), HTML/HTM. "
            "Use this tool when you need the full content of a file or to read it sequentially. "
            "PAGINATION: Files larger than 10,000 characters are split into pages of 10,000 chars each. "
            "When the response ends with `**Page #X. Total pages: Y**` it means there is more content available -- "
            "either call the tool again with the next `page` value, or switch to the RAG search tool for question-answering. "
            "Always start with page=1. Provide the exact `file_url` from the user's attachment."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_url": {
                    "type": "string",
                    "description": "URL of the file to extract content from (use the URL provided in the user's attachment).",
                },
                "page": {
                    "type": "integer",
                    "default": 1,
                    "description": "For large documents pagination is enabled. Each page consists of 10000 characters.",
                },
            },
            "required": ["file_url"],
        }

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        file_url = arguments["file_url"]
        page = arguments.get("page", 1)
        if page is None:
            page = 1

        stage = tool_call_params.stage

        stage.append_content("## Request arguments: \n")
        stage.append_content(f"**File URL**: {file_url}\n\r")
        if page > 1:
            stage.append_content(f"**Page**: {page}\n\r")
        stage.append_content("## Response: \n")

        extractor = DialFileContentExtractor(endpoint=self.endpoint, api_key=tool_call_params.api_key)
        content = extractor.extract_text(file_url)

        if not content:
            content = "Error: File content not found."
        elif len(content) > 10_000:
            page_size = 10_000
            total_pages = (len(content) + page_size - 1) // page_size
            if page < 1:
                page = 1
            if page > total_pages:
                content = f"Error: Page {page} does not exist. Total pages: {total_pages}"
            else:
                start_index = (page - 1) * page_size
                end_index = start_index + page_size
                page_content = content[start_index:end_index]
                content = f"{page_content}\n\n**Page #{page}. Total pages: {total_pages}**"

        stage.append_content(f"```text\n\r{content}\n\r```\n\r")

        return content
