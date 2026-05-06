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
        # TODO: set as False since we will have custom variant of representation in Stage
        raise NotImplementedError()

    @property
    def name(self) -> str:
        # TODO: provide self-descriptive name
        raise NotImplementedError()

    @property
    def description(self) -> str:
        # TODO: provide tool description that will help LLM to understand when to use this tools and cover 'tricky'
        #  moments (not more 1024 chars)
        raise NotImplementedError()

    @property
    def parameters(self) -> dict[str, Any]:
        # TODO: provide tool parameters JSON Schema:
        #  - file_url is string, required
        #  - page is integer, by default 1, description: "For large documents pagination is enabled. Each page consists of 10000 characters."
        raise NotImplementedError()

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. Load arguments with `json`
        # 2. Get `file_url` from arguments
        # 3. Get `page` from arguments (if none, set as 1 by default)
        # 4. Get stage from `tool_call_params`
        # 5. Append content to stage: "## Request arguments: \n"
        # 6. Append content to stage: `f"**File URL**: {file_url}\n\r"`
        # 7. If `page` more than 1 then append content to stage: `f"**Page**: {page}\n\r"`
        # 8. Append content to stage: "## Response: \n"
        # 9. Implement `task.utils.dial_file_conent_extractor`, create DialFileContentExtractor and call `extract_text`
        #    method as `content`
        # 10. If no `content` present then set it as "Error: File content not found."
        # 11. If `content` len is more than 10_000 then we need to enable pagination:
        #       - create variable `page_size` as 10_000
        #       - calculate total pages, formula: (`content len` + `page_size` - 1) // `page_size`
        #       - if `page` is less then 1 (potential hallucination from LLM) then set it as 1
        #       - otherwise check if page > total pages (potential hallucination), it yes then set `content` as
        #         `f"Error: Page {page} does not exist. Total pages: {total_pages}"`
        #       - prepare `start_index`: `(page - 1) * page_size`
        #       - prepare `end_index`: `start_index + page_size`
        #       - get page content from `content` that will start with `start_index` and end with `end_index`
        #       - set `content` as `f"{page_content}\n\n**Page #{page}. Total pages: {total_pages}**"` (It will show to
        #         LLM that it is not full content and it is pageable)
        # 12. Append content to stage: `f"```text\n\r{content}\n\r```\n\r"` (Will be shown in stage as markdown text)
        # 13. Return `content`
        raise NotImplementedError()
