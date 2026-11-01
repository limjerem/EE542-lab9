# Setup

Use Python 3.12. Keep credentials in local `.env` files.

## Group chat (Parts 1 and 4)

Configure `groupchat_app_src/.env` from its example. Start MySQL and the existing
Llama endpoint, then launch the website from the repository root:

```bash
RAG_REUSE_ONLY=1 .venv/bin/python -m uvicorn app:app --app-dir groupchat_app_src/backend --host 127.0.0.1 --port 8000
```

Open http://localhost:8000 and sign up or log in. The group chat now retrieves
from the shared upload knowledge base and uses the configured local Llama endpoint.
Uploads, failed-document retry, source passages and group history share one website.
The application extends the instructor's FastAPI/HTML template. Dependencies are in `groupchat_app_src/backend/requirements.txt`.
The merged backend uses bcrypt directly; the tested version is 4.3.0.

The local OpenAI embedding key is read from embedding/.env when not already set.
KB_DIR selects the shared document store; omit it to use kb_store. Existing vectors
have been reused locally; no bulk import is needed. Query vectors are cached, and
the answer runs on the local model. RAG_REUSE_ONLY=1 blocks uncached document
embeddings; omit it only when intentionally indexing new material. Original Part 3
indexes and database tables remain available independently.
For a completely cache-only verification, RAG_QUERY_REUSE_ONLY=1 also rejects
uncached question vectors. Leave that optional flag unset for normal new questions.

If Llama is stopped, run the existing build and weights from the parent Lab9 directory:

```bash
./llama.cpp/build/bin/llama-server \
  --model models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --alias lab9-llama \
  --host 127.0.0.1 --port 8001 --ctx-size 4096 --parallel 1 --n-gpu-layers all
```

Use one web writer process. Pending assistant jobs are in memory; completed answers
and their citations are stored in MySQL. See PART4_INTERFACES.md for the API contract.

## Part 3

Install `embedding/requirements.txt` into a separate virtual environment if needed.
The existing project `.venv` is ready; do not downgrade the working Conda environment.
Copy the configuration example to the ignored `embedding/.env.upload` and set the
OpenAI key, `mysql+pymysql` database URL, and absolute index paths. Existing
`embedding/.env` settings are also read. Environment variables take precedence.

```bash
RAG_REUSE_ONLY=1 .venv/bin/python -m streamlit run embedding/upload_app.py \
  --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Open http://localhost:8501. Process supports one or multiple PDF/TXT/MD/HTML files.
Load saved index restores vectors; Clear conversation clears session memory.
RAG_REUSE_ONLY prevents embedding uncached document text. Omit it only when
intentionally indexing new material. Questions and answers still use OpenAI.

The document library driver reads a folder and stores text in MySQL:

```bash
.venv/bin/python embedding/documents_cli.py --folder /path/to/documents --show-context
.venv/bin/python embedding/documents_cli.py --show-context
```

Type `/clear` or `exit`. Run without `--folder` to reuse the saved upload index.
The earlier standalone programs remain available as `embedding/rag_index.py`
and `embedding/chat_cli.py`; their original native index is kept intact.

## Private artifacts

Model weights, source PDFs, credentials and generated indexes are excluded from Git.
Restore these local artifacts after cloning. The upload library uses rag_documents,
rag_pages and rag_chunks, with LONGTEXT for full source text. Run one writer process
per upload index. Different browser sessions within that process share a writer lock.
