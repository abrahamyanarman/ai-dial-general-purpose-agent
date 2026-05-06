import json
from typing import Any

import faiss
import numpy as np
from aidial_client import AsyncDial
from aidial_sdk.chat_completion import Message, Role
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from task.tools.base import BaseTool
from task.tools.models import ToolCallParams
from task.tools.rag.document_cache import DocumentCache
from task.utils.dial_file_conent_extractor import DialFileContentExtractor

# TODO: provide system prompt for Generation step
_SYSTEM_PROMPT = """
You are a helpful assistant that answers questions based on the provided document context.
If the context doesn't contain the answer, say that you don't know based on the provided document.
Always cite the source if possible.
"""


class RagTool(BaseTool):
    """
    Performs semantic search on documents to find and answer questions based on relevant content.
    Supports: PDF, TXT, CSV, HTML.
    """

    def __init__(self, endpoint: str, deployment_name: str, document_cache: DocumentCache):
        #TODO:
        # 1. Set endpoint
        # 2. Set deployment_name
        # 3. Set document_cache. DocumentCache is implemented, relate to it as to centralized Dict with file_url (as key),
        #    and indexed embeddings (as value), that have some autoclean. This cache will allow us to speed up RAG search.
        # 4. Create SentenceTransformer and set is as `model` with:
        #   - model_name_or_path='all-MiniLM-L6-v2', it is self hosted lightwait embedding model.
        #     More info: https://medium.com/@rahultiwari065/unlocking-the-power-of-sentence-embeddings-with-all-minilm-l6-v2-7d6589a5f0aa
        #   - Optional! You can set it use CPU forcefully with `device='cpu'`, in case if not set up then will use GPU if it has CUDA cores
        # 5. Create RecursiveCharacterTextSplitter as `text_splitter` with:
        #   - chunk_size=500
        #   - chunk_overlap=50
        #   - length_function=len
        #   - separators=["\n\n", "\n", ". ", " ", ""]
        self._endpoint = endpoint
        self._deployment_name = deployment_name
        self._document_cache = document_cache
        self._model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    @property
    def show_in_stage(self) -> bool:
        # TODO: set as False since we will have custom variant of representation in Stage
        return False

    @property
    def name(self) -> str:
        # TODO: provide self-descriptive name
        return "rag_search"

    @property
    def description(self) -> str:
        # TODO: provide tool description that will help LLM to understand when to use this tools and cover 'tricky'
        #  moments (not more 1024 chars)
        return "Performs semantic search on large documents to find relevant information. Use this for PDF, TXT, CSV, or HTML files when you need to find specific answers in a large amount of text."

    @property
    def parameters(self) -> dict[str, Any]:
        # TODO: provide tool parameters JSON Schema:
        #  - request is string, description: "The search query or question to search for in the document", required
        #  - file_url is string, required
        return {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The search query or question to search for in the document"
                },
                "file_url": {
                    "type": "string",
                    "description": "The URL of the file to search in"
                }
            },
            "required": ["request", "file_url"]
        }


    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. Load arguments with `json`
        # 2. Get `request` from arguments
        # 3. Get `file_url` from arguments
        # 4. Get stage from `tool_call_params`
        # 5. Append content to stage: "## Request arguments: \n"
        # 6. Append content to stage: `f"**Request**: {request}\n\r"`
        # 7. Append content to stage: `f"**File URL**: {file_url}\n\r"`
        # 8. Create `cache_document_key`, it is string from `conversation_id` and `file_url`, with such key we guarantee
        #    access to cached indexes for one particular conversation,
        # 9. Get from `document_cache` by `cache_document_key` a cache
        # 10. If cache is present then set it as `index, chunks = cached_data` (cached_data is retrieved cache from 9 step),
        #     otherwise:
        #       - Create DialFileContentExtractor and extract text by `file_url` as `text_content`
        #       - If no `text_content` then appen to stage info about it ans return the string with the error that file content is not found
        #       - Create `chunks` with `text_splitter`
        #       - Create `embeddings` with `model`
        #       - Create IndexFlatL2 with `384` dimensions as `index` (more about IndexFlatL2 https://shayan-fazeli.medium.com/faiss-a-quick-tutorial-to-efficient-similarity-search-595850e08473)
        #       - Add to `index` np.array with created embeddings as type 'float32'
        #       - Add to `document_cache`
        # 11. Prepare `query_embedding` with model. You need to encode request as type 'float32'
        # 12. Through created index make search with `query_embedding`, `k` set as 3. As response we expect tuple of
        #     `distances` and `indices`
        # 13. Now you need to iterate through `indices[0]` and and by each idx get element from `chunks`, result save as `retrieved_chunks`
        # 14. Make augmentation
        # 15. Append content to stage: "## RAG Request: \n"
        # 16. Append content to stage: `ff"```text\n\r{augmented_prompt}\n\r```\n\r"` (will be shown as markdown text)
        # 17. Append content to stage: "## Response: \n"
        # 18. Now make Generation with AsyncDial (don't forget about api_version '025-01-01-preview, provide LLM with system prompt and augmented prompt and:
        #   - stream response to stage (user in real time will be able to see what the LLM responding while Generation step)
        #   - collect all content (we need to return it as tool execution result)
        # 19. return collected content
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        request = arguments.get("request")
        file_url = arguments.get("file_url")
        
        stage = tool_call_params.stage
        stage.append_content("## Request arguments: \n")
        stage.append_content(f"**Request**: {request}\n\r")
        stage.append_content(f"**File URL**: {file_url}\n\r")
        
        cache_document_key = f"{tool_call_params.conversation_id}_{file_url}"
        cached_data = self._document_cache.get(cache_document_key)
        
        if cached_data:
            index, chunks = cached_data
        else:
            extractor = DialFileContentExtractor(self._endpoint, tool_call_params.api_key)
            text_content = extractor.extract_text(file_url)
            if not text_content:
                stage.append_content("Error: File content not found.\n\r")
                return "Error: File content not found."
            
            chunks = self._text_splitter.split_text(text_content)
            embeddings = self._model.encode(chunks)
            index = faiss.IndexFlatL2(384)
            index.add(np.array(embeddings).astype('float32'))
            self._document_cache.set(cache_document_key, index, chunks)
            
        query_embedding = self._model.encode([request]).astype('float32')
        distances, indices = index.search(query_embedding, k=3)
        
        retrieved_chunks = [chunks[idx] for idx in indices[0] if idx != -1]
        augmented_prompt = self.__augmentation(request, retrieved_chunks)
        
        stage.append_content("## RAG Request: \n")
        stage.append_content(f"```text\n\r{augmented_prompt}\n\r```\n\r")
        stage.append_content("## Response: \n")
        
        client = AsyncDial(base_url=self._endpoint, api_key=tool_call_params.api_key, api_version='2025-01-01-preview')
        chunks_stream = await client.chat.completions.create(
            messages=[
                {"role": Role.SYSTEM.value, "content": _SYSTEM_PROMPT},
                {"role": Role.USER.value, "content": augmented_prompt}
            ],
            model=self._deployment_name,
            stream=True
        )
        
        collected_content = ""
        async for chunk in chunks_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                stage.append_content(content_chunk)
                collected_content += content_chunk
                
        return collected_content

    def __augmentation(self, request: str, chunks: list[str]) -> str:
        #TODO: make prompt augmentation
        context = "\n---\n".join(chunks)
        return f"Context information is below.\n---------------------\n{context}\n---------------------\nGiven the context information and not prior knowledge, answer the query.\nQuery: {request}\nAnswer: "
