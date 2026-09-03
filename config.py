"""
Central configuration for Enterprise AI Agent (personal local build).
Change values here rather than hunting through the other files.
"""

# --- Ollama models ---
# Chat model currently installed on this machine:
CHAT_MODEL = "llama3.1:8b"

# Embedding model currently installed on this machine:
EMBED_MODEL = "nomic-embed-text:latest"


# --- Layer 1: chunking ---
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


# --- Layer 2: vector store ---
VECTOR_DB_DIR = "./local_workspace_db"
VECTOR_COLLECTION_NAME = "workspace_documents"


# --- Layer 3: chat history ---
SQLITE_DB_PATH = "./history.db"
HISTORY_MESSAGES_FOR_CONTEXT = 5


# --- Retention policy ---
# Applies to both vector store and chat history.
RETENTION_DAYS = 30


# --- Retrieval ---
TOP_K_DOCS = 3