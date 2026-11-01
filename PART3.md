# Lab 9 Part 3: contributor's Windows review

The Windows contributor reviewed baseline commit
`1a4703d4f76e9367626ae54ee073ee0fa6a5be3a`, reproduced defects, added fixes, and
reports real OpenAI acceptance. The fixes were published in `bae98a2` and merged
through `ed37871`. Earlier wording that they were uncommitted is superseded.

The contributor used `C:\Project\EE542\Lab9`, a separate root `.venv` with Python
3.13.6, and Streamlit at http://127.0.0.1:8501. The backend virtual environment was
reserved for Parts 1/2. Current WSL setup is documented separately in `docs/SETUP.md`.

## Behavior and fixes

The application entry point is `embedding/upload_app.py`; `embedding/app.py` is the
original instructor example. Load saved index restores the existing library.
Process accepts single/multiple PDF, TXT, MD and HTML files. Retrieved passages
include the filename and physical PDF page. Clear conversation resets session
history while retaining SQL text and saved vectors.

| Reproduced issue | Published fix |
|---|---|
| A search could pair old FAISS positions with newly published metadata | Lock loading and retain a matching index/document snapshot per query |
| Windows non-UTF-8 defaults could corrupt metadata | Read metadata and CURRENT explicitly as UTF-8 |
| Older answers lost their retrieved passages after another question | Save sources alongside each answer in session state |
| RAG_REUSE_ONLY from merged settings was ignored | Pass the configured value into VectorStore while retaining environment fallback |
| Provider quota errors were unclear | Return actionable credit guidance without exposing provider bodies/keys |

The update adds five regression tests, `fonttools` for PDF font parsing, and optional
`PLAYWRIGHT_BROWSER_CHANNEL=chrome` support. Offline test doubles reproduce faults;
they are distinct from the contributor's reported real OpenAI runs.

## Contributor-reported acceptance

| Check | Recorded result | Referenced artifact |
|---|---|---|
| Regression tests | 12 passed on the earlier branch | `local-tests.txt` |
| Dependency consistency | pip check passed | `pip-check.txt` |
| Course PDF index | 124 pages, 771 vectors, 1536 dimensions | `native-index.json`, `native-index-build.txt` |
| MySQL / persisted library | 5 documents, 128 pages, 784 chunks/vectors | `library-verification.json` |
| Deduplication/cache reload | Passed without additional requests in that check | `library-verification.txt` |
| Browser uploads | Six scenarios passed | `upload-ui.json` |
| Real OpenAI conversation / CLI | Nine checks passed | `live-conversation.json`, `cli-live.txt` |
| Real OpenAI browser Q&A | Five checks passed | `live-browser.json` |
| Unicode Q&A / console encoding | Passed | `chinese-acceptance.json`, `cli-chinese.txt` |
| Parts 1/2 preservation | 22 protected file hashes unchanged | `summary.json` |

Models recorded by the contributor: `text-embedding-3-small` and `gpt-6-luna`.
An initial quota error was resolved before the reported successful runs. The
initial error record is referenced as `openai-connection-initial-quota.json`.
Most detailed artifacts in this table were not included in the pushed tree;
this checkout includes the updated `results/library.json`, `results/tests.txt`,
`results/upload-ui.json` and upload screenshot. Missing artifacts are not treated
as independent WSL acceptance.

## Recorded example

Question: "According to the ADS cookbook, how does tuning differ from optimization?"

Recorded answer: Tuning is a manual process that changes component values while
observing performance. Optimization changes values automatically to meet specified
goals, with citation [1]. A follow-up identified optimization as automated and
tuning as manual. A question about tomorrow's Los Angeles weather was declined
because the retrieved documents did not contain weather information.

The contributor references `embedding-example.json` and `embedding-example.npy`
for a source passage, retrieval similarity, vector components and a complete
L2-normalized 1536-dimensional vector. Those files were not pushed. Physical page 1
of a single-page excerpt may correspond to page 5 of the original course PDF.

Referenced screenshots under `screenshots/` show the library, answers, follow-up,
source expansion and cleared state. They remain on the contributor's machine.

## Windows reproduction

Run from `C:\Project\EE542\Lab9` in PowerShell:

```powershell
.\scripts\start_part3.ps1
.\scripts\start_part3.ps1 -Stop
```

The script manages only port 8501. Restart after changing local model/API settings.
Equivalent direct start and CLI commands:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m streamlit run embedding/upload_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
.\.venv\Scripts\python.exe -B -X utf8 .\embedding\documents_cli.py --show-context
.\.venv\Scripts\python.exe -B -X utf8 .\embedding\documents_cli.py --folder "C:\path\to\documents" --show-context
```

Type `/clear` or `exit`. Stop the upload writer before batch ingestion; one writer
process is supported per index. Ordinary CLI questions can use the saved library.

Private configuration is in `embedding/.env.upload`. Native vectors are under
`embedding/index_data`, upload generations/cache under `embedding/upload_index`,
and fixture excerpts under `local_artifacts/part3-upload-fixtures`. SQL uses
`rag_documents`, `rag_pages` and `rag_chunks`. Credentials and source artifacts
remain ignored. Memory retains the last six turns and is session-local.

Recheck with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
$env:RAG_REUSE_ONLY='1'
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_library.py
$env:PLAYWRIGHT_BROWSER_CHANNEL='chrome'
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_upload_ui.py
```

`scripts/verify_part3_live.py` and `scripts/verify_part3_browser.py` make real OpenAI
calls and replace their output files; do not rerun them merely to duplicate an
already successful paid check. The merged WSL review reuses existing document
vectors and keeps its own current results under `results/merge-review`.
