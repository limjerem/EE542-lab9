# Lab 9 Part 4 — ADS Study Companion

Part 4 is implemented as an ADS learning application for EE/RF engineering students. The website and Android TWA share one authenticated, document-grounded assistant. It reuses the teammate's Part 3 retrieval and conversation code in `lab9_core`; the formal collection is separate from Part 3 upload experiments.

## Current application

- Website: `http://localhost:8000/ads/`
- Current HTTPS/TWA launch address: `https://2dfe01690acad3.lhr.life/ads/`
- Android name: **ADS Study**, version **2.0 (2)**
- Package: `com.helloworld.groupchat.twa`
- Final APK and all experiment evidence: `outputs/part4/`
- Existing group chat: `http://localhost:8000/`
- Part 3 upload administration: `http://localhost:8501/` after running its existing startup script.

The lab's existing account works. A new lab account can also be created from Sign in. Passwords are hashed by the existing backend. OpenAI receives the submitted question, recent context and retrieved excerpts, as described in the app. No API key is included in the APK or frontend.

## Target users and curated collection

The application helps students understand simulation, tuning, optimization, and EM setup. It accepts English and Chinese questions, supports follow-ups, and shows the source edition, original excerpt and one-based physical PDF page for each citation.

| Primary publisher source | Edition | PDF pages | Selected chunks |
| --- | --- | ---: | ---: |
| [Circuit Design Cookbook 2.0](https://www.keysight.com/us/en/assets/7018-04800/application-notes/5992-0707.pdf) | ADS 2011 examples | 124 | 763 |
| [S-Parameter Simulation](https://edadownload.software.keysight.com/eedl/ads/2011_01/pdf/cktsimsp.pdf) | ADS 2011.01 | 30 | 107 |
| [Tuning, Optimization, and Statistical Design](https://edadownload.software.keysight.com/eedl/ads/2011_01/pdf/optstat.pdf) | ADS 2011.01 | 145 | 839 |
| [EM Simulation](https://edadownload.software.keysight.com/eedl/ads/2011/pdf/em.pdf) | ADS 2011 September | 163 | 843 |
| **Total** | **ADS 2011 family** | **462** | **2,552** |

`part4/corpus.json` records URLs, editions, SHA-256 checksums and exclusions. Cover/legal/front matter is excluded from retrieval; exact duplicate chunks and very short fragments are excluded. Chunks are at most 500 characters with overlap. The source collection is coherent around the same ADS generation; answers explicitly acknowledge that these documents cannot establish the ADS 2026 interface.

The supplied cookbook PDF is reused. Additional publisher PDFs are downloaded into ignored `local_artifacts/part4/corpus/`; full manuals are not committed or bundled with report evidence.

## Implementation

`part4/app.py` composes the original FastAPI app with `/ads/` and `/api/ads/`. The original group-chat routes remain available. `part4/service.py` uses the teammate's `DocumentChat` and `VectorStore`, with `text-embedding-3-small` and the configured `gpt-6-luna` answer model. Retrieval uses six passages; conversation context restores the last six successful turns.

The native FAISS index contains 2,552 normalized 1,536-dimensional vectors. The existing cookbook embedding cache supplied 763 matching vectors; only 1,789 new chunk embeddings were requested. The original `embedding/index_data` remains intact.

MySQL formal tables are `ads_documents` (4), `ads_document_pages` (462) and `ads_document_chunks` (2,552). `ads_conversations` and `ads_turns` store each account's questions, answers, retrieval query and attributed passages. The original Part 3 tables still contain 5 uploaded documents, 128 pages and 784 chunks.

Conversation ownership is enforced before retrieval. Repeated requests with the same UUID return the stored result without another model request. Failed answers are not added to history; invalid source labels are rejected. Limits are 2,000 input characters, 50 successful turns per conversation, 10 requests per user per minute and 25 globally per minute. New conversation keeps saved history. Navigation guards prevent delayed old-history responses from replacing a newly started conversation.

## Run from the requested mother directory

All Python commands use the existing virtual environment. Run PowerShell in `C:\Project\EE542\Lab9`:

```powershell
.\scripts\start_part4.ps1
```

To start/reuse the authorized localhost.run tunnel and refresh the Android configuration:

```powershell
.\scripts\start_part4.ps1 -Tunnel
```

The helper only replaces a verified, recorded Lab9 website process on port 8000. It retains the original group-chat routes and does not stop the Llama or Part 3 services. To stop only the Part 4 website:

```powershell
.\scripts\start_part4.ps1 -Stop
```

Free tunnel domains can rotate. The helper reads the latest assigned address. Whenever the address changes, generate APKs again in Android Studio and reinstall the new APK; keep the computer, website and SSH tunnel running during the demonstration. This is a temporary demonstration deployment. [localhost.run documents free-domain changes](https://localhost.run/docs/faq#my-free-domain-keeps-changing).

## Rebuild the collection if necessary

The existing private `embedding/.env.upload` supplies `OPENAI_API_KEY`, `DATABASE_URL`, `EMBEDDING_MODEL` and `OPENAI_CHAT_MODEL`. Keep this file out of Git and do not paste its contents into reports.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\part4\requirements.txt
.\.venv\Scripts\python.exe -B -m part4.prepare
```

The preparation step fetches missing pinned PDFs, verifies their checksums, reuses cached vectors and publishes only the formal ADS tables. Restart the website after preparing a new generation. A new corpus or uncached vectors use the configured paid API.

For Android, open the existing `groupchat_app_src/twa_android_src` project in Android Studio and use **Generate APKs**. The app launches the `/ads/` path, while Digital Asset Links associates the HTTPS origin with the package and actual signing certificate. The delivered debug APK is for the lab demonstration.

## Verified results and report evidence

All checks were performed locally on 2026-10-31 (Los Angeles time). No video was recorded; Android screenshots are original `adb exec-out screencap -p` captures.

- **17 automated backend tests passed**, including prior Part 3 tests and new ownership, idempotency, history and failure-persistence checks.
- Desktop Chrome: real model answer, clickable source, MySQL persistence, reload, new conversation, cross-account access denial, mobile navigation and no horizontal overflow.
- A separate browser regression delayed an old conversation response and proved it cannot overwrite a newer New conversation action; it used no model call.
- Android API 37 emulator: installed version 2.0, actual S-parameter answer, Chinese follow-up with context rewriting, references, reload, saved conversation reopening, library and ADS 2026 version-boundary response.
- Public HTTPS validated normally. Google Digital Asset Links validated the package/certificate. Android reported the domain as verified. The page reported secure standalone mode; the visible UI hierarchy contained no Chrome address bar/toolbar, and web content filled the viewport. No Chrome trust-bypass command-line file was installed.

Useful evidence files:

- `corpus-verification.json`: extraction, selection and embedding totals.
- `desktop-verification.json`, `android-verification.json`, `ui-race-verification.json`: actual checks and questions/results.
- `google-dal.json`, `assetlinks.json`, `android-app-links.txt`, `android-window.xml`: HTTPS/TWA association evidence.
- `apk-signature.txt`, `build-verification.json`: final APK signature, hash and build information.
- `screenshots/desktop-01-home.png`, `desktop-02-library.png`, `desktop-03-source.png`, `desktop-04-answer.png`: desktop views.
- `screenshots/android-08-clean-chat.png` through `android-13-final.png`: clean Android captures after restarting the lab browser without saving a password or editing an image.

To repeat checks, install the optional verification dependencies in the same virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\part4\requirements-test.txt
.\.venv\Scripts\python.exe -B -m pytest -q tests
.\.venv\Scripts\python.exe -B .\scripts\verify_part4_ui_race.py
.\.venv\Scripts\python.exe -B .\scripts\verify_part4_desktop.py
.\.venv\Scripts\python.exe -B .\scripts\verify_part4_android.py
```

Desktop/Android acceptance runs intentionally make a few real model requests. Android checks require the installed current-origin APK and running emulator. These scripts keep synthetic lab accounts and successful turns as evidence.
