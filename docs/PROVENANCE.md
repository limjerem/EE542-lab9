# Source provenance

`groupchat_app_src/` and the original Streamlit example in `embedding/app.py` derive
from the instructor's assignment template. Their local working versions are preserved.
The standalone `embedding/rag_index.py` and `embedding/chat_cli.py` implement PDF
indexing and conversational retrieval developed for this lab.

The upload application, document library, SQLAlchemy Core storage, conversation
adapter, persistence layer and regression checks were implemented for this project
with Codex assistance. The conversation adapter reuses the standalone CLI prompts;
the library can reuse the standalone native FAISS vectors without embedding them again.
Git commits use the configured author N0tSync <tyzccs6@gmail.com>. This description
does not assign personal authorship of the instructor's template or library code.

Third-party Python dependencies are identified in requirements files. Local PDF
content and model weights are not included in this repository.
