"""
Layer 1: Dynamic Data Ingestion Layer (The Influx)

Handles a file the moment it's uploaded: extract raw text, split into
overlapping chunks, hand off to Layer 2 (vector_store) for embedding + storage.
"""

import os

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config import CHUNK_SIZE, CHUNK_OVERLAP
from db import vector_store

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


def _extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext in (".txt", ".md", ".log"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise ValueError(f"Unsupported file type: {ext}")


def ingest_file(file_path: str) -> int:
    """
    Entry point the UI calls the moment a file is dropped in.
    Returns the number of chunks stored, so the UI can show quick feedback.
    """
    text = _extract_text(file_path)
    if not text.strip():
        return 0

    chunks = _splitter.split_text(text)
    source_name = os.path.basename(file_path)
    vector_store.add_documents(chunks, source=source_name)
    return len(chunks)
