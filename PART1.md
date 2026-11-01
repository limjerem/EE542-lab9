# Lab 9 Part 1: contributor's Windows setup

This page records the Windows contributor's setup at `C:\Project\EE542\Lab9`.
The shared application now also includes the Part 4 document assistant. For the
current WSL setup and integration evidence, see `docs/SETUP.md` and
`docs/PART4_VALIDATION.md`.

## Recorded environment

- Website: http://localhost:8000, FastAPI with HTML/CSS/JavaScript.
- MySQL: `127.0.0.1:3306/groupchat`, application user `chatuser`.
- Local model: Meta Llama 3.1 8B Instruct, Q4_K_M, 4096 context, RTX 4060 CUDA.
- Model endpoint: `http://127.0.0.1:8001/v1`, alias `llama-3.1-8b-instruct`.
- Python: `groupchat_app_src\backend\.venv`, Python 3.13.6.

These are the contributor's machine settings, not the WSL machine specification.
Credentials remain in ignored configuration files. Create a local test account
rather than relying on a password published in documentation.

## Start and stop on Windows

Confirm MySQL is running, then use PowerShell:

```powershell
Set-Location 'C:\Project\EE542\Lab9'
.\scripts\start_part1.ps1
.\scripts\start_part1.ps1 -Stop
```

The script reuses ready services and stops only processes it recorded with matching
start times. MySQL is managed separately. Logs are written under `work\logs`.
The combined Part 4 backend also requires the dependencies in
`groupchat_app_src/backend/requirements.txt`; the imported requirements.lock.txt
records the earlier Part 1 environment only.

## Demonstration and checks

Register or log in, send ordinary messages, then send a question containing an ASCII
or full-width question mark. Compare two browser sessions, reload saved history,
and log out. Usernames need at least three characters after trimming. Passwords
need at least eight characters and must fit within 72 UTF-8 bytes.

The contributor's `scripts/verify_part1.py` checks real MySQL, authentication,
WebSocket broadcasts, local model replies, bcrypt hashes and persistence. It
removes only its own test data and writes `work/part1-verification.json`. The
original general-chat answers are historical; the combined Part 4 assistant is
restricted to retrieved documents. The verification script now handles queued
reply status events and selects cached ADS questions when the shared knowledge
base is ready. Its merged WSL run passed 42 checks; a separate 17-check browser
run is recorded by `scripts/verify_part4.py`.

Merged changes include direct bcrypt, asynchronous password hashing, credential
validation, authenticated WebSockets, reconnect/history synchronization, message
ID deduplication, Unicode question marks and send/error feedback.

## Model provenance

The contributor recorded llama.cpp b12023 / CUDA 12.4 and the
[bartowski model repository](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)
at revision `bf5b95e96dac0462e2a09145ec66cae9a3f12067`. Model/runtime hashes are
referenced in `tools/llama.cpp/provenance.json` on that machine. Those ignored
artifacts were not included in the remote update and were not reverified on WSL.
