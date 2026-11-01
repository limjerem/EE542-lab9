r"""
document list + upload API for the knowledge base.

Tables (created automatically, same MySQL database as the chat):
    kb_documents  one row per file: name, sha256 (unique), status, error, full text
    kb_chunks     every 500-char chunk with its page number

Status flow:   processing -> indexed
                          \-> failed  (error saved; POST /api/documents/{id}/retry)

Endpoints (all need the login token):
    GET    /api/documents              list with status / pages / chunks / error
    POST   /api/documents              upload one or many files (form field "files")
    POST   /api/documents/{id}/retry   re-index a failed document from its stored chunks
    DELETE /api/documents/{id}         remove document, chunks and vectors

Duplicate rule: same file content (sha256) is never embedded twice.
    already indexed -> returns "duplicate", nothing is re-vectorised
    previously failed -> uploading it again counts as a retry

Hook-up in app.py (3 lines):
    from documents_api import create_documents_router, init_documents_db
    app.include_router(create_documents_router(current_user))   # after current_user is defined
    await init_documents_db()                                    # inside lifespan(), before yield
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import DateTime, Integer, String, Text, delete, func, select, update
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # groupchat_app_src/.env
REPO_ROOT = Path(__file__).resolve().parents[2]          # .../<repo>/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from lab9_core.kb import (SUPPORTED_EXTENSIONS, ExtractionError, chunk_pages,  # noqa: E402
                          extract_pages, get_kb)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
DATABASE_URL = os.getenv("DATABASE_URL",
                         "mysql+asyncmy://chatuser:chatpass@localhost:3306/groupchat")

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)
BigText = Text().with_variant(LONGTEXT(), "mysql")


class KBBase(DeclarativeBase):
    pass


class KBDocument(KBBase):
    __tablename__ = "kb_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    num_pages: Mapped[int] = mapped_column(Integer, default=0)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(BigText)
    uploaded_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(),
                                                 onupdate=func.now())


class KBChunk(KBBase):
    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)


async def init_documents_db():
    """Create tables, then make MySQL and the vector store agree:
    rows marked 'indexed' whose vectors are missing, or stuck in 'processing'
    after a crash, are marked 'failed' so they show a Retry button."""
    async with engine.begin() as conn:
        await conn.run_sync(KBBase.metadata.create_all)
    indexed_ids = await asyncio.to_thread(lambda: get_kb().indexed_doc_ids())
    async with Session() as s:
        docs = (await s.execute(select(KBDocument.id, KBDocument.status))).all()
        broken = [i for i, st in docs
                  if st == "processing" or (st == "indexed" and i not in indexed_ids)]
        if broken:
            await s.execute(update(KBDocument).where(KBDocument.id.in_(broken))
                            .values(status="failed", error="Not in vector index (interrupted?). Retry."))
            await s.commit()


def _doc_json(d: KBDocument) -> dict:
    return {"id": d.id, "filename": d.filename, "status": d.status, "error": d.error,
            "pages": d.num_pages, "chunks": d.num_chunks,
            "created_at": d.created_at.isoformat() if d.created_at else None}


async def _index(doc_id: int) -> dict:
    """Embed a stored document's chunks into the vector store, recording success/failure."""
    async with Session() as s:
        doc = await s.get(KBDocument, doc_id)
        rows = (await s.execute(select(KBChunk.page_no, KBChunk.content)
                                .where(KBChunk.document_id == doc_id)
                                .order_by(KBChunk.chunk_index))).all()
        doc.status, doc.error = "processing", None
        await s.commit()
    try:
        await asyncio.to_thread(get_kb().index_document, doc_id, doc.filename,
                                [(p, c) for p, c in rows])
        status, error = "indexed", None
    except Exception as exc:  # embedding API down, bad key, quota, ...
        status, error = "failed", str(exc)[:1000]
    async with Session() as s:
        await s.execute(update(KBDocument).where(KBDocument.id == doc_id)
                        .values(status=status, error=error))
        await s.commit()
        return _doc_json(await s.get(KBDocument, doc_id))


async def ingest_bytes(filename: str, data: bytes, user_id: Optional[int] = None) -> dict:
    """Shared by the upload endpoint and ingest_kb.py.  Returns the document json plus
    "result": "indexed" | "duplicate" | "retried" | "failed"."""
    filename = Path(filename).name
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"{filename}: only PDF, TXT, MD and HTML are supported")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{filename} is larger than {MAX_UPLOAD_MB} MB")
    sha = hashlib.sha256(data).hexdigest()

    async with Session() as s:
        existing = await s.scalar(select(KBDocument).where(KBDocument.sha256 == sha))
    if existing:
        if existing.status == "indexed" and await asyncio.to_thread(get_kb().has_document, existing.id):
            return {**_doc_json(existing), "result": "duplicate"}
        if existing.status == "processing":
            return {**_doc_json(existing), "result": "processing"}
        out = await _index(existing.id)  # failed before -> retry
        return {**out, "result": "retried" if out["status"] == "indexed" else "failed"}

    try:
        pages = await asyncio.to_thread(extract_pages, data, filename)
    except ExtractionError as exc:
        raise HTTPException(400, str(exc))
    chunks = chunk_pages(pages)

    async with Session() as s:
        doc = KBDocument(filename=filename, sha256=sha, status="processing",
                         num_pages=len(pages), num_chunks=len(chunks),
                         text="\n\n".join(t for _, t in pages), uploaded_by=user_id)
        s.add(doc)
        try:
            await s.flush()
        except Exception:  # two people uploaded the same file at the same moment
            await s.rollback()
            existing = await s.scalar(select(KBDocument).where(KBDocument.sha256 == sha))
            return {**_doc_json(existing), "result": "duplicate"}
        s.add_all(KBChunk(document_id=doc.id, page_no=p, chunk_index=i, content=c)
                  for i, (p, c) in enumerate(chunks))
        await s.commit()
        doc_id = doc.id

    out = await _index(doc_id)
    return {**out, "result": out["status"]}


def create_documents_router(current_user) -> APIRouter:
    router = APIRouter(prefix="/api/documents", tags=["documents"])

    @router.get("")
    async def list_documents(user=Depends(current_user)):
        async with Session() as s:
            docs = (await s.execute(select(KBDocument).order_by(KBDocument.id.desc()))).scalars().all()
        return {"documents": [_doc_json(d) for d in docs]}

    @router.post("")
    async def upload_documents(files: List[UploadFile] = File(...), user=Depends(current_user)):
        results = []
        for f in files:   # one bad file doesn't stop the others
            try:
                results.append(await ingest_bytes(f.filename or "upload", await f.read(), user.id))
            except HTTPException as exc:
                results.append({"filename": f.filename, "result": "rejected", "error": exc.detail})
        return {"results": results}

    @router.post("/{doc_id}/retry")
    async def retry_document(doc_id: int, user=Depends(current_user)):
        async with Session() as s:
            doc = await s.get(KBDocument, doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        if doc.status == "processing":
            raise HTTPException(409, "Document is already being processed")
        return await _index(doc_id)

    @router.delete("/{doc_id}")
    async def delete_document(doc_id: int, user=Depends(current_user)):
        async with Session() as s:
            doc = await s.get(KBDocument, doc_id)
            if doc is None:
                raise HTTPException(404, "Document not found")
            await asyncio.to_thread(get_kb().remove_document, doc_id)
            await s.execute(delete(KBChunk).where(KBChunk.document_id == doc_id))
            await s.delete(doc)
            await s.commit()
        return {"ok": True}

    return router
