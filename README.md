# EE542 Lab 9

An ADS/RF chatbot project with shared web chat, document uploads, MySQL storage,
cached retrieval, and a separate ADS Study Companion website and Android TWA.

The shared group chat and upload integration are in `groupchat_app_src/`.
Standalone document RAG is in `embedding/` and `lab9_core/`. See
[setup](docs/SETUP.md), [shared chat interfaces](docs/PART4_INTERFACES.md), and
[shared chat validation](docs/PART4_VALIDATION.md).

The **ADS Study Companion** in `part4/` uses a curated ADS 2011 collection and
persistent per-user study conversations. See [its setup, sources and verification](PART4.md).
Start with `scripts/start_part4.ps1`; the study app is at
`http://localhost:8000/ads/`, and the shared group chat remains at `/`.

Local Word2Vec and custom histogram experiments are in `part5/`.
See [Part 5](docs/PART5.md) for the experiment protocol and results.
