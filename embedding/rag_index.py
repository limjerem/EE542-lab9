#!/usr/bin/env python3
"""Build and query a persistent PDF index for EE542 Lab 9 Part 3.

Place this file beside embedding/.env, then run:
    python rag_index.py build "Ads cookbook .pdf"
    python rag_index.py search "How do I tune a circuit in ADS?"

Build calls the OpenAI embedding API for document chunks. Search loads the
saved index and calls that API only for the question. This stage retrieves
source passages; it does not yet generate an LLM answer or write to MySQL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 64


def make_embeddings(model: str):
    from dotenv import load_dotenv
    from langchain_openai import OpenAIEmbeddings

    load_dotenv(BASE_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError(f"Set OPENAI_API_KEY in {BASE_DIR / '.env'}")
    return OpenAIEmbeddings(
        model=model,
        chunk_size=BATCH_SIZE,
        max_retries=5,
        request_timeout=60,
    )


def extract_chunks(pdf_paths: list[Path]) -> tuple[list[dict], list[dict]]:
    from langchain_text_splitters import CharacterTextSplitter
    from pypdf import PdfReader

    splitter = CharacterTextSplitter(
        separator="\n", chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP, length_function=len,
    )
    fallback = CharacterTextSplitter(
        separator="", chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP, length_function=len,
    )
    records: list[dict] = []
    sources: list[dict] = []
    seen: set[Path] = set()
    for supplied_path in pdf_paths:
        path = supplied_path.expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        reader = PdfReader(path)
        source_id = len(sources)
        sources.append({
            "source_id": source_id,
            "filename": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pages": len(reader.pages),
        })
        before = len(records)
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            for piece in splitter.split_text(text):
                # CharacterTextSplitter may exceed its target for a long
                # separator-free section. Split that section again if needed.
                pieces = fallback.split_text(piece) if len(piece) > CHUNK_SIZE else [piece]
                for chunk in pieces:
                    if chunk.strip():
                        records.append({
                            "chunk_id": len(records),
                            "source_id": source_id,
                            "filename": path.name,
                            "page": page_number,
                            "text": chunk,
                        })
        print(f"{path.name}: {len(reader.pages)} pages, {len(records) - before} chunks", flush=True)
    if not records:
        raise ValueError("No text chunks found. Use PDFs with extractable text.")
    return records, sources


def build_index(pdf_paths: list[Path], index_dir: Path, model: str = DEFAULT_MODEL) -> dict:
    import faiss
    import numpy as np

    index_dir = index_dir.expanduser().resolve()
    if index_dir.exists():
        raise FileExistsError(
            f"Index directory already exists: {index_dir}. "
            "Use the search command, or choose a new --index-dir before build."
        )
    records, sources = extract_chunks(pdf_paths)
    embeddings = make_embeddings(model)
    vectors = []
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        vectors.extend(embeddings.embed_documents([record["text"] for record in batch]))
        print(f"Embedded {start + len(batch)}/{len(records)} chunks", flush=True)

    matrix = np.ascontiguousarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(records) or matrix.shape[1] == 0:
        raise ValueError("The embedding API returned an unexpected vector shape.")
    if not np.isfinite(matrix).all() or (np.linalg.norm(matrix, axis=1) == 0).any():
        raise ValueError("The embedding API returned invalid vectors.")
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    payload = {
        "format_version": 1,
        "embedding_model": model,
        "dimension": int(matrix.shape[1]),
        "metric": "cosine",
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "sources": sources,
        "chunks": records,
    }

    # Publish both files together, only after all API requests succeed.
    index_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rag-index-", dir=index_dir.parent) as temporary:
        stage = Path(temporary) / "index"
        stage.mkdir()
        faiss.write_index(index, str(stage / "index.faiss"))
        (stage / "chunks.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        stage.rename(index_dir)
    print(f"Saved {index.ntotal} vectors, dimension {index.d}, to {index_dir}", flush=True)
    return payload


def search_index(index_dir: Path, question: str, k: int = 4) -> list[dict]:
    import faiss
    import numpy as np

    if not question.strip() or k < 1:
        raise ValueError("Supply a nonempty question and a positive k.")
    index_dir = index_dir.expanduser().resolve()
    payload = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    index = faiss.read_index(str(index_dir / "index.faiss"))
    records = payload["chunks"]
    if index.ntotal != len(records) or index.d != payload["dimension"]:
        raise ValueError("Index and chunk metadata do not match.")
    embeddings = make_embeddings(payload["embedding_model"])
    query = np.ascontiguousarray([embeddings.embed_query(question)], dtype=np.float32)
    if query.shape != (1, index.d):
        raise ValueError("Query embedding dimension does not match the saved index.")
    if not np.isfinite(query).all() or np.linalg.norm(query) == 0:
        raise ValueError("The embedding API returned an invalid query vector.")
    faiss.normalize_L2(query)
    scores, ids = index.search(query, min(k, index.ntotal))
    return [
        {**records[int(chunk_id)], "score": float(score)}
        for score, chunk_id in zip(scores[0], ids[0]) if chunk_id >= 0
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, default=BASE_DIR / "index_data")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Embed PDFs and save a new index.")
    build.add_argument("pdfs", nargs="+", type=Path)
    build.add_argument("--model", default=DEFAULT_MODEL)
    search = commands.add_parser("search", help="Retrieve passages from a saved index.")
    search.add_argument("question")
    search.add_argument("-k", type=int, default=4)
    args = parser.parse_args()
    try:
        if args.command == "build":
            build_index(args.pdfs, args.index_dir, args.model)
        else:
            for rank, hit in enumerate(search_index(args.index_dir, args.question, args.k), start=1):
                print(f"\nResult {rank}: cosine={hit['score']:.4f}, {hit['filename']}, page {hit['page']}")
                print(hit["text"])
    except Exception as exc:
        message = str(exc)
        secret = os.getenv("OPENAI_API_KEY", "")
        if secret:
            message = message.replace(secret, "[redacted]")
        print(f"{type(exc).__name__}: {message}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
