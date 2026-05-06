import io
from pathlib import Path

import pdfplumber
import pandas as pd
from aidial_client import Dial
from bs4 import BeautifulSoup


class DialFileContentExtractor:

    def __init__(self, endpoint: str, api_key: str):
        #TODO:
        # Set Dial client with endpoint as base_url and api_key
        raise NotImplementedError()

    def extract_text(self, file_url: str) -> str:
        #TODO:
        # 1. Download with Dial client file by `file_url` (files -> download)
        # 2. Get downloaded file name and content
        # 3. Get file extension, use for this `Path(filename).suffix.lower()`
        # 4. Call `__extract_text` and return its result
        raise NotImplementedError()

    def __extract_text(self, file_content: bytes, file_extension: str, filename: str) -> str:
        """Extract text content based on file type."""
        #TODO:
        # Wrap in `try-except` block:
        # try:
        #   1. if `file_extension` is '.txt' then return `file_content.decode('utf-8', errors='ignore')`
        #   2. if `file_extension` is '.pdf' then:
        #       - load it with `io.BytesIO(file_content)`
        #       - with pdfplumber.open PDF files bites
        #       - iterate through created pages adn create array with extracted page text
        #       - return it joined with `\n`
        #   3. if `file_extension` is '.csv' then:
        #       - decode `file_content` with encoding 'utf-8' and errors='ignore'
        #       - create csv buffer from `io.StringIO(decoded_text_content)`
        #       - read csv with pandas (pd) as dataframe
        #       - return dataframe to markdown (index=False)
        #   4. if `file_extension` is in ['.html', '.htm'] then:
        #       - decode `file_content` with encoding 'utf-8' and errors='ignore'
        #       - create BeautifulSoup with decoded html content, features set as 'html.parser' as `soup`
        #       - remove script and style elements: iterate through `soup(["script", "style"])` and `decompose` those scripts
        #       - return `soup.get_text(separator='\n', strip=True)`
        #   5. otherwise return it as decoded `file_content` with encoding 'utf-8' and errors='ignore'
        # except:
        #   print an error and return empty string
        raise NotImplementedError()
