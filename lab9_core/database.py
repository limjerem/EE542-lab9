"""Transactional storage of source text, pages, and ordered retrieval chunks."""
from __future__ import annotations

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, MetaData, String,
                        Table, Text, create_engine, delete, func, insert, select)
from sqlalchemy.dialects.mysql import LONGTEXT

schema = MetaData()
large_text = Text().with_variant(LONGTEXT(), 'mysql')
sources = Table('rag_documents', schema,
    Column('id', Integer, primary_key=True),
    Column('filename', String(255), nullable=False),
    Column('sha256', String(64), unique=True, nullable=False),
    Column('num_pages', Integer, nullable=False),
    Column('text', large_text, nullable=False),
    Column('uploaded_at', DateTime, server_default=func.now()))
pages = Table('rag_pages', schema,
    Column('id', Integer, primary_key=True),
    Column('document_id', ForeignKey('rag_documents.id', ondelete='CASCADE'), nullable=False),
    Column('page_no', Integer, nullable=False),
    Column('text', large_text, nullable=False))
chunks = Table('rag_chunks', schema,
    Column('id', Integer, primary_key=True),
    Column('document_id', ForeignKey('rag_documents.id', ondelete='CASCADE'), nullable=False),
    Column('page_no', Integer, nullable=False),
    Column('chunk_index', Integer, nullable=False),
    Column('content', Text, nullable=False))


class Database:
    def __init__(self, url):
        self.engine = create_engine(url, pool_pre_ping=True)
        schema.create_all(self.engine)

    def record(self, filename, digest, page_text, documents):
        """Preserve text and chunk order together; repeat content is idempotent."""
        with self.engine.begin() as connection:
            identifier = connection.scalar(select(sources.c.id).where(sources.c.sha256 == digest))
            if identifier is None:
                identifier = connection.execute(insert(sources).values(
                    filename=filename, sha256=digest, num_pages=len(page_text),
                    text='\n\n'.join(page_text))).inserted_primary_key[0]
                connection.execute(insert(pages), [dict(document_id=identifier, page_no=i, text=t)
                                                   for i,t in enumerate(page_text,1)])
            desired = [(d.metadata['page'], d.page_content) for d in documents]
            current = connection.execute(select(chunks.c.page_no, chunks.c.content)
                .where(chunks.c.document_id == identifier).order_by(chunks.c.chunk_index)).all()
            if [tuple(row) for row in current] != desired:
                connection.execute(delete(chunks).where(chunks.c.document_id == identifier))
                if desired:
                    connection.execute(insert(chunks), [dict(document_id=identifier,
                        page_no=p, chunk_index=i, content=t) for i,(p,t) in enumerate(desired)])
        return identifier

    def list_sources(self):
        with self.engine.connect() as connection:
            return connection.execute(select(sources.c.filename, sources.c.num_pages)
                                      .order_by(sources.c.id)).all()

    def counts(self):
        with self.engine.connect() as connection:
            return {table.name:connection.scalar(select(func.count()).select_from(table))
                    for table in (sources,pages,chunks)}
