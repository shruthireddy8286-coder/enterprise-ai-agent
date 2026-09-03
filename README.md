# Enterprise AI Agent (personal, local-first)

A fully local, privacy-preserving personal AI assistant: retrieval-augmented
generation over your own uploaded documents, short-term conversation memory,
and a lightweight agentic orchestrator -- all running on-device through
Ollama. Nothing leaves the machine at any point.

## Setup

1. Install [Ollama](https://ollama.com), then pull the two models used here:
   ```
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```
   Confirm the exact names with `ollama list` and match them in `config.py`
   (`CHAT_MODEL` / `EMBED_MODEL`).
2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run it:
   ```
   streamlit run app.py
   ```

## Architecture

Four layers, following a standard RAG + short-term-memory pattern:

- **Layer 1 - Ingestion** (`ingestion.py`): uploaded PDF/TXT/MD files are
  split into 800-token chunks with 150-token overlap.
- **Layer 2 - Vector memory** (`db/vector_store.py`): chunks are embedded
  with `nomic-embed-text` and stored in a persistent ChromaDB collection.
  Every chunk carries a timestamp so it can later be pruned.
- **Layer 3 - Chat memory** (`db/chat_memory.py`): every message (both
  sides) is logged to SQLite with a timestamp, session-scoped so multiple
  conversations don't bleed into each other.
- **Layer 4 - Orchestration** (`agent_graph.py` + `agents.py`): a LangGraph
  graph makes one real routing decision per message -- whether the query
  needs a document search at all -- before recalling recent history and
  generating a reply with the chat model.

## Local action commands ("open youtube", "book a cab", "play games"...)

`web_actions.py` adds a second, earlier routing decision in `app.py`,
*before* the LangGraph pipeline: it checks whether the message is a literal
"open X" command or a task-style request (booking a cab, bus, train, flight,
hotel, or movie ticket; ordering food; playing online games), and if so
opens the right site directly in your machine's default browser via
Python's built-in `webbrowser` module -- no LLM call, no retrieval, instant
response. Anything that doesn't match falls straight through to the normal
RAG + chat pipeline untouched. Examples:

| You type | Opens |
|---|---|
| `open youtube` / `open flipkart` / `open zoom` / ... (~90 sites known by name) | that site directly |
| `open github.com` (any raw domain) | that domain |
| `book a cab` / `need a ride` | Uber |
| `book bus tickets` | RedBus |
| `book a train` / `train booking` | IRCTC |
| `book a flight` | MakeMyTrip |
| `book movie tickets` | BookMyShow |
| `order food` | Swiggy |
| `order groceries` | Blinkit |
| `order medicine` | PharmEasy |
| `book a hotel` / `book a room` | Booking.com |
| `buy online` / `shop online` | Amazon |
| `play some games` / `open online games` | CrazyGames |
| `listen to music` / `play a song` | Spotify |
| `watch a movie` / `watch a show` | Netflix |
| `start a video call` / `join a meeting` | Google Meet |
| `take a course` / `learn something new` | Coursera |
| `find a job` | LinkedIn Jobs |
| `track my parcel` | FedEx |
| `check the weather` | Weather.com |
| `read the news` | Google News |

Add or change destinations by editing `KNOWN_SITES` (direct name → URL,
grouped by category) or `INTENT_ROUTES` (trigger phrases → URL) at the top
of `web_actions.py`.

## Reconstructed modules

`db/chat_memory.py` and `db/vector_store.py` implement the SQLite and
ChromaDB storage described above, matching the interface `agents.py` and
`ingestion.py` expect (`chat_memory.add_message`, `chat_memory.list_sessions`,
`vector_store.similarity_search`, `vector_store.add_documents`, etc.).

## Retention

Both stores enforce a 30-day retention window, pruned once per app
startup (`chat_memory.prune_older_than`, `vector_store.prune_older_than`).
This isn't automatic just because data lives in a vector store -- every
stored row/chunk carries an explicit timestamp, and pruning is an active
delete-by-timestamp step, not something Chroma or SQLite do on their own.

## Known limitations

- Response latency is noticeably slower than a cloud API on CPU-only
  hardware -- an intentional tradeoff for the zero-data-egress guarantee,
  not a bug. See `tests/sample_questions.md` for the evaluation approach
  used to validate retrieval quality despite this.
- Single-user only: no auth, no multi-tenancy. Out of scope by design for
  a personal tool.