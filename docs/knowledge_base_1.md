# Knowledge Base and Document Upload

## Files
| File | Purpose |
|---|---|
| `lab9_core/kb.py` | Text extraction, chunking (500 chars, 100 overlap), embedding API calls, vector storage (`kb_store/`), and similarity search. Has no FastAPI dependency, so the RAG service can import it directly. |
| `groupchat_app_src/backend/documents_api.py` | Upload, list, retry, and delete endpoints. Stores text in the MySQL tables `kb_documents` and `kb_chunks`. |
| `groupchat_app_src/backend/ingest_kb.py` | Bulk-imports a folder of documents, using the same code path as the upload endpoint. |
| `data/SOURCES.md` | Record of data sources and selection criteria. |

## Integrating with app.py
```python
from documents_api import create_documents_router, init_documents_db   # after load_dotenv()

app.include_router(create_documents_router(current_user))   # after app and current_user are defined

# inside lifespan(), before yield:
await init_documents_db()
```
If `app.py` already defines `/api/documents` routes or a `kb_documents` table, remove them to avoid conflicts.

## Environment variables (.env)
```
OPENAI_API_KEY=sk-...                    # used for embeddings
EMBEDDING_MODEL=text-embedding-3-small
# To use a local llama.cpp server for embeddings instead (run as a separate server):
# llama-server -m nomic-embed-text-v1.5.Q8_0.gguf --embeddings --port 8002
# EMBEDDING_API_BASE=http://localhost:8002/v1
# EMBEDDING_MODEL=nomic-embed-text
KB_DIR=                                   # empty = <repo>/kb_store
MAX_UPLOAD_MB=25
```
After changing the embedding model, delete `kb_store/` and retry or re-import all documents, since the vector dimensions will differ.

Add `kb_store/` to `.gitignore`.

## Searching the knowledge base (RAG service)
```python
import asyncio
from lab9_core.kb import get_kb

hits = await asyncio.to_thread(get_kb().search, query, 4)
# hits = [{"text": "...", "source": "ADS_Circuit_Design_Cookbook.pdf", "page": 47,
#          "doc_id": 1, "score": 0.83}, ...]   sorted by similarity, highest first; [] if the knowledge base is empty
```
`score` is cosine similarity. Questions outside the knowledge base usually score lower, so a threshold (for example, < 0.3) can be used to detect insufficient context. Tune the threshold against real data before relying on it.

## Document API
All requests require `Authorization: Bearer <token>`.

`GET /api/documents`
```json
{"documents": [{"id": 1, "filename": "a.pdf", "status": "indexed", "error": null,
                "pages": 124, "chunks": 755, "created_at": "..."}]}
```
`status`: `processing` (in progress) / `indexed` (done) / `failed` (see `error`; the UI should offer a Retry button)

`POST /api/documents` (multipart, field name `files`, multiple files allowed)
```json
{"results": [{"id": 1, "filename": "a.pdf", "status": "indexed", "result": "indexed", ...},
             {"filename": "b.docx", "result": "rejected", "error": "b.docx: only PDF, TXT, MD and HTML are supported"}]}
```
`result` values:
- `indexed`: added successfully
- `duplicate`: already exists; not re-embedded
- `retried`: failed previously, succeeded this time
- `failed`: embedding failed (see `error`)
- `rejected`: unsupported type or too large
- `processing`: currently being processed

`POST /api/documents/{id}/retry`: returns the document JSON; returns 409 if the document is already processing.

`DELETE /api/documents/{id}`: returns `{"ok": true}`.

Large PDFs (100+ pages) take 20–60 seconds to process, so the frontend should show a loading state.

## Verification
```bash
cd groupchat_app_src/backend
pip install pypdf beautifulsoup4 numpy httpx langchain-text-splitters python-multipart
python ingest_kb.py <path-to-data-folder>   # expect 6 "indexed", about 1208 chunks total
python ingest_kb.py <path-to-data-folder>   # second run: 6 "duplicate", nothing re-embedded
```
| Check | How to test | Expected result |
|---|---|---|
| PDF/TXT/HTML upload | Upload each type via the web page or `/docs` | `result: indexed` |
| Text stored in MySQL | `SELECT id, filename, status, num_chunks FROM kb_documents;` | One row per document, with matching rows in `kb_chunks` |
| Vectors stored | `kb_store/meta.json` exists; answers cite sources | Chunk count matches MySQL |
| No duplicate embedding | Upload the same file again | `result: duplicate`; chunk count in `meta.json` unchanged |
| Retry after failure | Set a wrong `OPENAI_API_KEY`, upload → `failed`; fix the key, restart, retry | `failed` → `indexed` |
| Unsupported format | Upload a `.docx` | `result: rejected` |

Without a frontend, use FastAPI's built-in docs at http://localhost:8000/docs: get a token from `/api/login`, click **Authorize**, and paste it.

## Test status
- **Tested** with a stub embedding function: extraction and chunking of all 6 documents (max 500 characters per chunk), re-indexing without duplicates, index unchanged when embedding fails, persistence across restarts, deletion, and rejection of unsupported or empty files.
- **Not yet tested end-to-end:** `documents_api.py` and `ingest_kb.py` against a live MySQL database and the OpenAI API.
