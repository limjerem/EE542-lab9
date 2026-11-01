"""
Knowledge base core .  No FastAPI / SQLAlchemy here, so it can be
tested on its own and imported by both documents_api.py (A) and rag_service.py (B).

    extract_pages(data, filename)  -> [(page_no, text)]       pdf / txt / md / html
    chunk_pages(pages)             -> [(page_no, chunk_text)] 500 chars, 100 overlap
    get_kb().index_document(doc_id, filename, chunks)         embed + store (replaces old vectors)
    get_kb().remove_document(doc_id)
    get_kb().has_document(doc_id)
    get_kb().search(query, k=4)    -> [{"text","source","page","doc_id","score"}]   <- B uses this

Vectors are kept in a small numpy store on disk (KB_DIR/vectors.npy + meta.json),
written atomically, so a crash during indexing never corrupts the existing index.

Embeddings: any OpenAI-compatible /v1/embeddings endpoint.
    OpenAI    : EMBEDDING_API_BASE=https://api.openai.com/v1  OPENAI_API_KEY=sk-...
    llama.cpp : EMBEDDING_API_BASE=http://localhost:8002/v1   (llama-server ... --embeddings)
"""
from __future__ import annotations

import io
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".htm"}
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


class ExtractionError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_pages(data: bytes, filename: str) -> List[Tuple[int, str]]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(f"Unsupported file type: {ext or filename}")
    if ext == ".pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [(i, _clean(p.extract_text() or "")) for i, p in enumerate(reader.pages, 1)]
        except Exception as exc:
            raise ExtractionError(f"Could not read PDF {filename}: {exc}") from exc
    else:
        text = data.decode("utf-8", errors="ignore")
        if ext in (".html", ".htm"):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text("\n")
        pages = [(1, _clean(text))]
    pages = [(n, t) for n, t in pages if t]
    if not pages:
        raise ExtractionError(f"No text found in {filename} (scanned PDF? it needs OCR first)")
    return pages


# --------------------------------------------------------------------------- #
# Chunking (LangChain CharacterTextSplitter, as the handout asks)
# --------------------------------------------------------------------------- #
def _split(text: str) -> List[str]:
    try:
        from langchain_text_splitters import CharacterTextSplitter
        return CharacterTextSplitter(separator="\n", chunk_size=CHUNK_SIZE,
                                     chunk_overlap=CHUNK_OVERLAP, length_function=len
                                     ).split_text(text)
    except ImportError:  # same behaviour, used only if langchain isn't installed
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        chunks, cur = [], []
        for p in parts:
            if cur and len("\n".join(cur + [p])) > CHUNK_SIZE:
                chunks.append("\n".join(cur))
                while cur and (len("\n".join(cur)) > CHUNK_OVERLAP
                               or len("\n".join(cur + [p])) > CHUNK_SIZE):
                    cur.pop(0)
            cur.append(p)
        if cur:
            chunks.append("\n".join(cur))
        return chunks


def _hard_split(chunk: str) -> List[str]:
    """CharacterTextSplitter keeps a single line longer than chunk_size as one big
    chunk (common in HTML/release notes). Cut those on word boundaries with overlap."""
    if len(chunk) <= CHUNK_SIZE:
        return [chunk]
    words, out, cur = chunk.split(), [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > CHUNK_SIZE:
            out.append(" ".join(cur))
            while cur and len(" ".join(cur)) > CHUNK_OVERLAP:
                cur.pop(0)
        cur.append(w[:CHUNK_SIZE])
    if cur:
        out.append(" ".join(cur))
    return out


def chunk_pages(pages: Sequence[Tuple[int, str]]) -> List[Tuple[int, str]]:
    return [(n, piece) for n, t in pages for c in _split(t) for piece in _hard_split(c)
            if piece.strip()]


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def openai_compatible_embedder(batch_size: int = 64) -> Callable[[List[str]], np.ndarray]:
    import httpx

    base = os.getenv("EMBEDDING_API_BASE", "https://api.openai.com/v1").rstrip("/")
    key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    headers = {"Authorization": f"Bearer {key}"} if key else {}

    def embed(texts: List[str]) -> np.ndarray:
        out = []
        with httpx.Client(timeout=120) as client:
            for i in range(0, len(texts), batch_size):
                batch = [t[:8000] for t in texts[i:i + batch_size]]
                r = client.post(f"{base}/embeddings", headers=headers,
                                json={"model": model, "input": batch})
                if r.status_code >= 400:
                    raise RuntimeError(f"Embedding API error {r.status_code}: {r.text[:300]}")
                data = sorted(r.json()["data"], key=lambda d: d["index"])
                out.extend(d["embedding"] for d in data)
        return np.asarray(out, dtype=np.float32)

    return embed


def _unit(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


# --------------------------------------------------------------------------- #
# Vector store + knowledge base
# --------------------------------------------------------------------------- #
class KnowledgeBase:
    def __init__(self, directory: str | Path, embed_fn: Callable[[List[str]], np.ndarray]):
        self.dir = Path(directory)
        self.embed_fn = embed_fn
        self.lock = threading.RLock()
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.meta: List[dict] = []
        self._load()

    # ---- persistence ---- #
    def _load(self):
        v, m = self.dir / "vectors.npy", self.dir / "meta.json"
        if v.exists() and m.exists():
            self.vectors = np.load(v)
            self.meta = json.loads(m.read_text(encoding="utf-8"))
            if len(self.meta) != len(self.vectors):  # inconsistent -> start clean, docs get re-indexed
                self.vectors, self.meta = np.zeros((0, 0), dtype=np.float32), []

    def _save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp_v, tmp_m = self.dir / "vectors.tmp.npy", self.dir / "meta.tmp.json"
        np.save(tmp_v, self.vectors)
        tmp_m.write_text(json.dumps(self.meta, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_v, self.dir / "vectors.npy")
        os.replace(tmp_m, self.dir / "meta.json")

    # ---- writes ---- #
    def index_document(self, doc_id: int, filename: str, chunks: Sequence[Tuple[int, str]]) -> int:
        """Embed all chunks of one document and store them, replacing any old vectors
        for that doc_id. Embedding happens BEFORE touching the store, so if the API
        fails nothing changes and the document can simply be retried."""
        if not chunks:
            raise ValueError("document has no chunks")
        vecs = _unit(self.embed_fn([c for _, c in chunks]))
        if len(vecs) != len(chunks):
            raise RuntimeError("embedding API returned the wrong number of vectors")
        with self.lock:
            if self.vectors.size and self.vectors.shape[1] != vecs.shape[1]:
                raise RuntimeError(
                    f"embedding size changed ({self.vectors.shape[1]} -> {vecs.shape[1]}); "
                    "delete the KB_DIR folder and re-index all documents")
            self._drop(doc_id)
            new_meta = [{"doc_id": doc_id, "source": filename, "page": p, "chunk": i, "text": c}
                        for i, (p, c) in enumerate(chunks)]
            self.vectors = vecs if not self.vectors.size else np.vstack([self.vectors, vecs])
            self.meta.extend(new_meta)
            self._save()
        return len(chunks)

    def _drop(self, doc_id: int):
        keep = [i for i, m in enumerate(self.meta) if m["doc_id"] != doc_id]
        if len(keep) != len(self.meta):
            self.vectors = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
            self.meta = [self.meta[i] for i in keep]

    def remove_document(self, doc_id: int):
        with self.lock:
            self._drop(doc_id)
            self._save()

    # ---- reads ---- #
    def has_document(self, doc_id: int) -> bool:
        return any(m["doc_id"] == doc_id for m in self.meta)

    def indexed_doc_ids(self) -> set:
        return {m["doc_id"] for m in self.meta}

    def search(self, query: str, k: int = 4) -> List[dict]:
        with self.lock:
            if not self.meta:
                return []
            vectors, meta = self.vectors, list(self.meta)
        q = _unit(self.embed_fn([query]))[0]
        sims = vectors @ q
        top = np.argsort(-sims)[:k]
        return [{**{key: meta[i][key] for key in ("text", "source", "page", "doc_id")},
                 "score": float(sims[i])} for i in top]


_kb: Optional[KnowledgeBase] = None
_kb_lock = threading.Lock()


def get_kb() -> KnowledgeBase:
    """Shared instance (the same object for documents_api and rag_service)."""
    global _kb
    with _kb_lock:
        if _kb is None:
            default = Path(__file__).resolve().parent.parent / "kb_store"
            _kb = KnowledgeBase(os.getenv("KB_DIR") or default, openai_compatible_embedder())
        return _kb
