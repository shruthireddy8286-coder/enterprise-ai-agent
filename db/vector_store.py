"""
db/vector_store.py

Layer 2: persistent vector memory (ChromaDB), embedded with the local
`nomic-embed-text` model via Ollama.

Every stored chunk carries a `timestamp` metadata field so retention can be
enforced later via prune_older_than() -- Chroma does not expire data on its
own; pruning is an explicit delete-by-timestamp step run once per app
startup (see app.py's cached _startup()).
"""

from datetime import datetime, timedelta
from typing import Dict, List
from uuid import uuid4

import chromadb
from langchain_ollama import OllamaEmbeddings

from config import (
    EMBED_MODEL,
    RETENTION_DAYS,
    TOP_K_DOCS,
    VECTOR_COLLECTION_NAME,
    VECTOR_DB_DIR,
)
from logging_config import get_logger

logger = get_logger(__name__)

_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
_collection = _client.get_or_create_collection(
    name=VECTOR_COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)
_embeddings = OllamaEmbeddings(model=EMBED_MODEL)


def add_documents(chunks: List[str], source: str) -> None:
    """Embed and permanently store a list of text chunks from one uploaded file."""
    if not chunks:
        return

    vectors = _embeddings.embed_documents(chunks)
    now = datetime.utcnow().isoformat()
    ids = [str(uuid4()) for _ in chunks]
    metadatas = [
        {"source": source, "timestamp": now, "chunk_index": i}
        for i in range(len(chunks))
    ]

    _collection.add(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)
    logger.info("vector_store: added %d chunk(s) from %s", len(chunks), source)


def similarity_search(query: str, top_k: int = TOP_K_DOCS) -> List[Dict]:
    """Return the top_k most relevant chunks as [{source, text}, ...]."""
    if _collection.count() == 0:
        return []

    query_vector = _embeddings.embed_query(query)
    results = _collection.query(query_embeddings=[query_vector], n_results=top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    return [
        {"source": meta.get("source", "unknown"), "text": doc_text}
        for doc_text, meta in zip(documents, metadatas)
    ]


def document_count() -> int:
    """Total number of chunks currently stored (used in the app.py header caption)."""
    return _collection.count()


def prune_older_than(days: int = RETENTION_DAYS) -> int:
    """Delete chunks older than `days`. Returns the number of chunks deleted."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    existing = _collection.get(include=["metadatas"])

    ids_to_delete = [
        _id
        for _id, meta in zip(existing["ids"], existing["metadatas"])
        if meta.get("timestamp", "") < cutoff
    ]
    if ids_to_delete:
        _collection.delete(ids=ids_to_delete)

    logger.info("vector_store: pruned %d chunk(s) older than %d day(s)", len(ids_to_delete), days)
    return len(ids_to_delete)
