import io
from pathlib import Path

import pdfplumber
import pandas as pd
from aidial_client import Dial
from bs4 import BeautifulSoup


class DialFileContentExtractor:

    def __init__(self, endpoint: str, api_key: str):
        self.client = Dial(base_url=endpoint, api_key=api_key)

    def extract_text(self, file_url: str) -> str:
        downloaded = self.client.files.download(file_url)
        # Aidial client returns object with `name` and `content` attributes (or dict-like)
        filename = getattr(downloaded, "name", None)
        content = getattr(downloaded, "content", None)
        if filename is None and isinstance(downloaded, dict):
            filename = downloaded.get("name")
            content = downloaded.get("content")
        if content is None:
            # Some versions return raw bytes
            content = downloaded
            filename = file_url

        file_extension = Path(filename or file_url).suffix.lower()
        return self.__extract_text(content, file_extension, filename or file_url)

    def __extract_text(self, file_content: bytes, file_extension: str, filename: str) -> str:
        """Extract text content based on file type."""
        try:
            if file_extension == ".txt":
                return file_content.decode("utf-8", errors="ignore")
            if file_extension == ".pdf":
                pdf_bytes = io.BytesIO(file_content)
                with pdfplumber.open(pdf_bytes) as pdf:
                    pages_text = [page.extract_text() or "" for page in pdf.pages]
                return "\n".join(pages_text)
            if file_extension == ".csv":
                decoded = file_content.decode("utf-8", errors="ignore")
                csv_buffer = io.StringIO(decoded)
                df = pd.read_csv(csv_buffer)
                return df.to_markdown(index=False)
            if file_extension in [".html", ".htm"]:
                decoded = file_content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(decoded, features="html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()
                return soup.get_text(separator="\n", strip=True)
            return file_content.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ Error during file content extraction for '{filename}': {e}")
            return ""
