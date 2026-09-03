"""
tests/test_vector_store.py

Covers: storing chunks and retrieving the top-k most relevant ones, document
counting, and retention pruning. The real Ollama embedding calls are
monkeypatched with deterministic fake vectors so these tests run fully
offline, and the module's Chroma collection is swapped for a temporary one
so tests never touch ./local_workspace_db.
"""

import chromadb

import db.vector_store as vector_store


class _FakeEmbeddings:
    """Stand-in for OllamaEmbeddings that needs no live Ollama server."""

    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768


def _use_temp_collection(tmp_path, monkeypatch, name="test_collection"):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma_test"))
    collection = client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
    monkeypatch.setattr(vector_store, "_collection", collection)
    monkeypatch.setattr(vector_store, "_embeddings", _FakeEmbeddings())
    return collection


def test_add_documents_and_similarity_search(tmp_path, monkeypatch):
    _use_temp_collection(tmp_path, monkeypatch)

    vector_store.add_documents(["Aegis Workspace stores everything locally."], source="notes.txt")

    results = vector_store.similarity_search("Where is data stored?", top_k=1)
    assert len(results) == 1
    assert results[0]["source"] == "notes.txt"
    assert "locally" in results[0]["text"]


def test_similarity_search_on_empty_store_returns_empty_list(tmp_path, monkeypatch):
    _use_temp_collection(tmp_path, monkeypatch)

    assert vector_store.similarity_search("anything") == []


def test_document_count(tmp_path, monkeypatch):
    _use_temp_collection(tmp_path, monkeypatch)

    assert vector_store.document_count() == 0
    vector_store.add_documents(["chunk one", "chunk two"], source="doc.txt")
    assert vector_store.document_count() == 2


def test_prune_older_than_removes_stale_chunks(tmp_path, monkeypatch):
    collection = _use_temp_collection(tmp_path, monkeypatch)

    vector_store.add_documents(["fresh chunk"], source="new.txt")

    # Manually insert an "old" chunk with a stale timestamp.
    collection.add(
        ids=["old-chunk-id"],
        embeddings=[[0.2] * 768],
        documents=["old chunk"],
        metadatas=[{"source": "old.txt", "timestamp": "2000-01-01T00:00:00", "chunk_index": 0}],
    )

    deleted = vector_store.prune_older_than(days=30)
    assert deleted == 1
    assert vector_store.document_count() == 1
