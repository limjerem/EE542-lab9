# Source provenance

`groupchat_app_src/` and the original Streamlit example in `embedding/app.py` derive
from the instructor's assignment template. Their local working versions are preserved.
The standalone `embedding/rag_index.py` and `embedding/chat_cli.py` implement PDF
indexing and conversational retrieval developed for this lab.

The upload application, document library, SQLAlchemy Core storage, conversation
adapter, persistence layer and regression checks were implemented for this project
with Codex assistance. The conversation adapter reuses the standalone CLI prompts;
the library can reuse the standalone native FAISS vectors without embedding them again.
The initial working snapshot was committed as N0tSync <tyzccs6@gmail.com> in 1a4703d.
The upload API/knowledge base arrived in 48f5208 by limjerem <limjerem@usc.edu>.
The Windows/Android work and Part 3 fixes arrived in 2d011e0 and bae98a2 by
Jason <jjjjjason9@gmail.com>, followed by merge ed37871. Their recorded Git authors
and history are retained. Part 4 B/C integration, English report translations
and merge-review validation were prepared with Codex assistance. The user
authorized their publication together with Part 5 under the existing Git identity,
N0tSync <tyzccs6@gmail.com>.

This description does not assign personal authorship of instructor templates or
third-party library code. Contributor-reported device outcomes are distinguished
from tests rerun on WSL; see MERGE_REVIEW.md.

Third-party Python dependencies are identified in requirements files. Local PDF
content and model weights are not included in this repository.

`part5/` and `tests/test_part5.py` were implemented for this project with Codex
assistance. Word2Vec training uses Gensim; k-means++ initialization, Lloyd updates,
empty-cluster recovery, histogram construction, retrieval and evaluation use our
NumPy implementation. No external clustering implementation or pretrained word
vectors are substituted. The evaluation questions/page labels were authored with
Codex assistance before the first training run and are not independently graded.
`results/part5/` records actual local runs, source hashes, configured Git identity
and the base commit used before publication. The experiment metadata preserves
the uncommitted state at measurement time. Part 4 source files were left unchanged
during the Part 5 implementation and experiments.
