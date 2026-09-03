"""
Enterprise AI Agent - personal local build
Run with:  streamlit run app.py
Requires Ollama running locally with `phi4-mini` and `nomic-embed-text` pulled.
"""

import uuid

import streamlit as st

from db import chat_memory, vector_store
from ingestion import ingest_file
from agents import chief_executive_respond_stream
from agent_graph import get_context
from web_actions import open_in_browser, parse_action_command
from logging_config import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Enterprise AI Agent (Personal)", page_icon="🧠")


@st.cache_resource
def _startup():
    """
    Runs once per app process, not once per interaction (Streamlit re-runs
    the whole script on every click/message, so this MUST be cached or
    you'd be re-pruning and re-initing the DB on every single message).
    """
    chat_memory.init_db()
    deleted_msgs = chat_memory.prune_older_than()
    vector_store.prune_older_than()
    return deleted_msgs


deleted_count = _startup()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []  # rendered messages for the active session

with st.sidebar:
    st.header("Chats")
    if st.button("+ New chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.caption("Past sessions (last 30 days)")
    for session_id, preview, last_active in chat_memory.list_sessions():
        label = (preview[:40] + "...") if len(preview) > 40 else preview
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(label, key=f"sess_{session_id}", use_container_width=True):
                st.session_state.session_id = session_id
                st.session_state.messages = [
                    {"role": "user" if sender == "user" else "assistant", "content": text}
                    for sender, text in chat_memory.get_all_messages(session_id)
                ]
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{session_id}"):
                chat_memory.delete_session(session_id)
                if session_id == st.session_state.session_id:
                    st.session_state.session_id = str(uuid.uuid4())
                    st.session_state.messages = []
                st.rerun()

    st.divider()
    if st.button("Clear ALL history", use_container_width=True):
        chat_memory.delete_all()
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

st.title("🧠 Enterprise AI Agent")
st.caption(
    f"Fully local · nothing leaves this machine · "
    f"{vector_store.document_count()} chunks in memory · "
    f"30-day retention (pruned {deleted_count} old messages on startup)"
)

# --- File upload bubble (Layer 1) ---
uploaded_file = st.file_uploader("Drop a file to add it to memory", type=["pdf", "txt", "md", "log"])
if uploaded_file is not None:
    temp_path = f"./_upload_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    n_chunks = ingest_file(temp_path)
    st.success(f"Stored {n_chunks} chunks from {uploaded_file.name}")

# --- Chat history (this browser tab only, for display) ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
prompt = st.chat_input(
    "Ask something, or say things like 'open youtube', 'book a cab', "
    "'book bus tickets', 'book a train', 'play some games'..."
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Log the user's message immediately -- this is the "is it actually stored?" step
    chat_memory.add_message(st.session_state.session_id, "user", prompt)

    # --- Local action commands: "open youtube", "book a cab", "play games", etc. ---
    # Checked BEFORE the retrieval/LLM pipeline so these fire instantly and
    # never consume a model call.
    action = parse_action_command(prompt)
    if action:
        display_name, url = action
        with st.chat_message("assistant"):
            launched = open_in_browser(url)
            if launched:
                reply = f"Opening **{display_name}** for you → {url}"
                st.success(reply)
            else:
                reply = (
                    f"I tried to open **{display_name}** but couldn't launch a "
                    f"browser from this environment. You can open it manually: {url}"
                )
                st.warning(reply)

        chat_memory.add_message(st.session_state.session_id, "agent", reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

    else:
        with st.chat_message("assistant"):
            try:
                with st.spinner("Deciding what context is needed..."):
                    # LangGraph orchestrator: classify -> (retrieve | skip) -> history.
                    # This is the real agentic decision point -- small talk skips
                    # the document search instead of always running it.
                    context = get_context(prompt, st.session_state.session_id)
                    doc_context = context["doc_context"]
                    history_context = context["history_context"]

                reply = st.write_stream(
                    chief_executive_respond_stream(prompt, doc_context, history_context)
                )

            except Exception as e:
                logger.exception("Message handling failed")
                st.error(
                    "Couldn't reach the local model. Check that Ollama is running "
                    "(`ollama serve`) and that the model name in config.py matches "
                    "`ollama list` exactly."
                )
                st.caption(f"Details: {e}")
                reply = None

            if reply:
                with st.expander("Context sent to the model this turn"):
                    st.markdown("**Retrieved document chunks (Agent 1):**")
                    st.code(doc_context)
                    st.markdown("**Recent conversation history (Agent 2):**")
                    st.code(history_context)

                chat_memory.add_message(st.session_state.session_id, "agent", reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})