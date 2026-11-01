# Setup

Use Python 3.12. Keep credentials in local `.env` files.

## Part 1

Configure `groupchat_app_src/.env` from its example. Start MySQL and the existing
Llama endpoint, then launch the website from the repository root:

```bash
.venv/bin/python -m uvicorn app:app --app-dir groupchat_app_src/backend --host 0.0.0.0 --port 8000
```

The application uses the instructor's FastAPI/HTML template with the local working
configuration. Dependencies are in `groupchat_app_src/backend/requirements.txt`.
The tested password packages are passlib 1.7.4 and bcrypt 4.0.1.

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
