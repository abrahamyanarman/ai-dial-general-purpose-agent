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

_SYSTEM_PROMPT = """You are a precise question-answering assistant whose answers are GROUNDED in the provided document excerpts.

Rules:
- Answer ONLY using the information present in the supplied "Context" passages. Do not rely on outside knowledge.
- If the context does not contain enough information to answer the question, say so explicitly and recommend that the user re-phrase, request a different page, or attach a more relevant file.
- Quote or closely paraphrase the relevant portions of the context. Be concise and structured.
- When the answer involves steps, list them in order. When it involves data, present it cleanly (tables / bullet lists).
- Never invent file URLs, page numbers, or facts that are not in the context.
"""


class RagTool(BaseTool):
    """
    Performs semantic search on documents to find and answer questions based on relevant content.
    Supports: PDF, TXT, CSV, HTML.
    """

    def __init__(self, endpoint: str, deployment_name: str, document_cache: DocumentCache):
        self.endpoint = endpoint
        self.deployment_name = deployment_name
        self.document_cache = document_cache
        self.model = SentenceTransformer(model_name_or_path="all-MiniLM-L6-v2", device="cpu")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    @property
    def show_in_stage(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "rag_search_tool"

    @property
    def description(self) -> str:
        return (
            "Performs Retrieval-Augmented Generation (RAG) over an attached document to ANSWER a specific question "
            "from its contents. Use this tool when: (a) the user asks a focused question about an attached file, "
            "or (b) the file is too large to read end-to-end via the file content extraction tool (i.e. you've seen "
            "`Total pages: N` with N > 1). The tool semantically searches the document and produces a grounded answer. "
            "Supported formats: PDF, TXT, CSV, HTML. Provide the user's exact question as `request` and the original "
            "`file_url` from the attachment. Prefer this tool over reading every page when the user wants a specific answer."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The search query or question to search for in the document",
                },
                "file_url": {
                    "type": "string",
                    "description": "URL of the document to search in (use the URL from the user's attachment).",
                },
            },
            "required": ["request", "file_url"],
        }

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        arguments = json.loads(tool_call_params.tool_call.function.arguments)
        request = arguments["request"]
        file_url = arguments["file_url"]

        stage = tool_call_params.stage

        stage.append_content("## Request arguments: \n")
        stage.append_content(f"**Request**: {request}\n\r")
        stage.append_content(f"**File URL**: {file_url}\n\r")

        cache_document_key = f"{tool_call_params.conversation_id}::{file_url}"
        cached_data = self.document_cache.get(cache_document_key)

        if cached_data is not None:
            index, chunks = cached_data
        else:
            extractor = DialFileContentExtractor(endpoint=self.endpoint, api_key=tool_call_params.api_key)
            text_content = extractor.extract_text(file_url)

            if not text_content:
                stage.append_content("\n**Error**: File content not found.\n")
                return "Error: File content not found. Please verify the file URL."

            chunks = self.text_splitter.split_text(text_content)
            embeddings = self.model.encode(chunks)
            index = faiss.IndexFlatL2(384)
            index.add(np.array(embeddings, dtype="float32"))
            self.document_cache.set(cache_document_key, index, chunks)

        query_embedding = np.array(self.model.encode([request]), dtype="float32")
        distances, indices = index.search(query_embedding, k=3)

        retrieved_chunks: list[str] = []
        for idx in indices[0]:
            if 0 <= idx < len(chunks):
                retrieved_chunks.append(chunks[idx])

        augmented_prompt = self.__augmentation(request, retrieved_chunks)

        stage.append_content("## RAG Request: \n")
        stage.append_content(f"```text\n\r{augmented_prompt}\n\r```\n\r")
        stage.append_content("## Response: \n")

        client = AsyncDial(base_url=self.endpoint, api_key=tool_call_params.api_key, api_version="2025-01-01-preview")

        collected_content = ""
        chunks_stream = await client.chat.completions.create(
            messages=[
                {"role": Role.SYSTEM.value, "content": _SYSTEM_PROMPT},
                {"role": Role.USER.value, "content": augmented_prompt},
            ],
            deployment_name=self.deployment_name,
            stream=True,
        )

        async for chunk in chunks_stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected_content += delta.content
                    stage.append_content(delta.content)

        return collected_content

    def __augmentation(self, request: str, chunks: list[str]) -> str:
        joined = "\n\n---\n\n".join(f"[Excerpt {i + 1}]\n{chunk}" for i, chunk in enumerate(chunks))
        return (
            "Answer the user's QUESTION using ONLY the information from the provided CONTEXT excerpts.\n"
            "If the answer is not contained in the context, reply that the document does not contain the answer.\n\n"
            f"CONTEXT:\n{joined}\n\n"
            f"QUESTION:\n{request}\n\n"
            "ANSWER:"
        )
