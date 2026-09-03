"""
Layer 4: Multi-Agent Orchestration Layer (The Controller)

Three roles, kept as plain functions for clarity:
  Agent 1 - Workspace Archivist : pulls relevant facts from ChromaDB
  Agent 2 - Context Historian   : pulls recent chat history from SQLite
  Agent 3 - Chief Executive     : Ollama chat model, consolidates both into a reply

Note: this is a fixed pipeline (retrieve -> history -> generate), not
agents making independent decisions. If you want that for the capstone
write-up, look at the LangGraph version noted in the README -- it lets
Agent 3 decide up front whether Agent 1 even needs to run (e.g. a plain
"hello" doesn't need a document search).
"""

from langchain_ollama import ChatOllama

from config import CHAT_MODEL
from db import chat_memory, vector_store
from logging_config import get_logger

logger = get_logger(__name__)

_llm = ChatOllama(model=CHAT_MODEL, temperature=0.3)

_SYSTEM_PROMPT = """You are a personal local AI assistant. Everything you \
know comes only from the two context blocks below -- your own uploaded \
documents and your recent conversation. If the answer isn't in either, \
say so plainly instead of guessing.

=== RELEVANT DOCUMENT EXCERPTS ===
{doc_context}

=== RECENT CONVERSATION ===
{history_context}
"""


def archivist_retrieve(query: str) -> str:
    """Agent 1: turn the question into the top-k matching document excerpts."""
    matches = vector_store.similarity_search(query)
    logger.info("Archivist retrieved %d chunk(s) for query", len(matches))
    if not matches:
        return "(no matching documents found in the workspace)"
    return "\n\n".join(
        f"[Source: {m['source']}]\n{m['text']}" for m in matches
    )


def historian_recall(session_id: str) -> str:
    """Agent 2: pull a short transcript of the recent conversation."""
    return chat_memory.summarize_recent_history(session_id)


def chief_executive_respond(query: str, doc_context: str, history_context: str) -> str:
    """Agent 3: consolidate both context sources into one final reply (non-streaming)."""
    system = _SYSTEM_PROMPT.format(doc_context=doc_context, history_context=history_context)
    try:
        response = _llm.invoke([
            ("system", system),
            ("human", query),
        ])
        return response.content
    except Exception:
        logger.exception("Ollama call failed - is the model pulled and Ollama running?")
        raise


def chief_executive_respond_stream(query: str, doc_context: str, history_context: str):
    """
    Agent 3, streaming version. Yields text chunks as they're generated so
    the UI can render token-by-token instead of waiting for the full reply.
    """
    system = _SYSTEM_PROMPT.format(doc_context=doc_context, history_context=history_context)
    try:
        for chunk in _llm.stream([
            ("system", system),
            ("human", query),
        ]):
            if chunk.content:
                yield chunk.content
    except Exception:
        logger.exception("Ollama streaming call failed - is the model pulled and Ollama running?")
        raise


def handle_user_message(session_id: str, query: str) -> str:
    """
    Full turn: retrieve docs, recall history, generate reply, log both
    sides of the exchange. This is the one function the UI calls per message.
    """
    chat_memory.add_message(session_id, "user", query)

    doc_context = archivist_retrieve(query)
    history_context = historian_recall(session_id)
    reply = chief_executive_respond(query, doc_context, history_context)

    chat_memory.add_message(session_id, "agent", reply)
    return reply