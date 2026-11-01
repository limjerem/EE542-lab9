# Validation

## Preserved baseline

The working Part 1 FastAPI source and the standalone PDF index/chat programs are
unchanged. Their file hashes were compared with the local baseline. The original
771-vector, 1536-dimensional native index remains intact. Part 1 registration,
login, group chat and local Llama replies were previously verified on this machine.
They were not rerun during this update.

## Document library

`results/library.json` and `results/library-run.txt` record a real MySQL check:

- Five documents, 128 pages, 784 chunks; full text, page text and chunk ordering retained.
- The original PDF produces the same 771 chunks, each at most 500 characters.
- Duplicate processing leaves SQL row counts and the saved vector count unchanged.
- Reload restores the 784-vector upload index.
- Both document and query embedding methods were blocked in this check: zero external API requests.

## Upload interface

`results/upload-ui.json`, `results/upload-ui-run.txt` and `results/upload-interface.png`
record a real Chromium session against the local Streamlit application. Single PDF,
multiple PDFs, text and HTML, repeated processing, loading saved vectors after a page
reload, and the clear button passed. Only cached course documents were selected.
No questions were submitted to OpenAI during this interface check.

## Local checks

`results/tests.txt` records seven passing regression tests. These exercise failed
publication, cached batch recovery, model mismatch, zero query rejection, upload
idempotency, chunk bounds and failed conversation turns. The installed environment
also passed `pip check`.

```bash
.venv/bin/python -m pytest tests -q
RAG_REUSE_ONLY=1 .venv/bin/python scripts/verify_library.py
PLAYWRIGHT_BROWSERS_PATH=/tmp/ee542-lab9-browsers \
  .venv/bin/python scripts/verify_upload_ui.py
```

The browser check requires the local PDF and generated excerpts in the ignored
`local_artifacts/part3-upload-fixtures` directory. The SQL check requires configured
local credentials and both saved indexes. These private artifacts are not included
in Git.

## Limits

The standalone CLI has prior real OpenAI question, follow-up and insufficient-context
validation. The new conversation adapter reuses its prompts; its failure/memory
behavior is covered locally. A new live answer was not requested merely to repeat
successful API calls. Source presence and local test doubles do not establish new
online answer acceptance.

Conversation memory is session-local. One writer process is supported per upload
index. Corrupt generations fail explicitly on load; existing native vectors and
cached batches avoid an automatic paid rebuild. A crash before a received API batch
has been committed to its cache can still require repeating that batch.
