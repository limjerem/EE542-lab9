"""Persistent formal corpus and per-user study conversations for Part 4."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, uuid
from sqlalchemy import (MetaData, Table, Column, String, Integer, DateTime, Text,
                        JSON, ForeignKey, create_engine, select, insert, update, delete)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.engine import make_url

schema = MetaData()
longtext = Text().with_variant(LONGTEXT(), 'mysql')
documents = Table('ads_documents', schema,
    Column('id', String(32), primary_key=True), Column('title', String(255)),
    Column('filename', String(255)), Column('edition', String(100)),
    Column('url', Text), Column('sha256', String(64)), Column('content_hash', String(64)),
    Column('page_count', Integer), Column('chunk_count', Integer))
pages = Table('ads_document_pages', schema,
    Column('id', Integer, primary_key=True),
    Column('source_id', ForeignKey('ads_documents.id'), nullable=False),
    Column('page_no', Integer), Column('text', longtext))
chunks = Table('ads_document_chunks', schema,
    Column('id', String(100), primary_key=True),
    Column('source_id', ForeignKey('ads_documents.id'), nullable=False),
    Column('page_no', Integer), Column('text', Text))
conversations = Table('ads_conversations', schema,
    Column('id', String(36), primary_key=True), Column('user_id', Integer, nullable=False),
    Column('title', String(160)), Column('created_at', DateTime), Column('updated_at', DateTime))
turns = Table('ads_turns', schema,
    Column('id', Integer, primary_key=True),
    Column('conversation_id', ForeignKey('ads_conversations.id'), nullable=False),
    Column('request_id', String(36), unique=True, nullable=False),
    Column('question', Text), Column('answer', longtext), Column('query', Text),
    Column('sources', JSON), Column('created_at', DateTime))

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None

class StudyStore:
    def __init__(self, url):
        parsed = make_url(url)
        if parsed.drivername.startswith('mysql'):
            parsed = parsed.set(drivername='mysql+pymysql')
        self.engine = create_engine(parsed, pool_pre_ping=True)
        schema.create_all(self.engine)

    def publish_corpus(self, manifest, extracted, selected):
        with self.engine.begin() as conn:
            for source in manifest['sources']:
                source_chunks = [d for d in selected if d.metadata['source_id'] == source['id']]
                texts = extracted[source['id']]
                fingerprint = hashlib.sha256(json.dumps([texts,[d.page_content for d in source_chunks]],ensure_ascii=False).encode()).hexdigest()
                previous = conn.execute(select(documents).where(documents.c.id == source['id'])).mappings().first()
                values = dict(title=source['title'],filename=source['filename'],edition=source['edition'],
                              url=source['url'],sha256=source['sha256'],content_hash=fingerprint,
                              page_count=len(texts),chunk_count=len(source_chunks))
                if previous:
                    conn.execute(update(documents).where(documents.c.id == source['id']).values(**values))
                else:
                    conn.execute(insert(documents).values(id=source['id'],**values))
                if previous and previous['content_hash'] == fingerprint:
                    continue
                conn.execute(delete(pages).where(pages.c.source_id == source['id']))
                conn.execute(delete(chunks).where(chunks.c.source_id == source['id']))
                conn.execute(insert(pages),[dict(source_id=source['id'],page_no=i,text=t) for i,t in enumerate(texts,1)])
                if source_chunks:
                    conn.execute(insert(chunks),[dict(id=d.metadata['chunk_id'],source_id=source['id'],page_no=d.metadata['page'],text=d.page_content) for d in source_chunks])

    def _owner(self, conn, user_id, conversation_id):
        row = conn.execute(select(conversations).where(conversations.c.id == conversation_id,
                                                       conversations.c.user_id == user_id)).mappings().first()
        if row is None:
            raise KeyError('Conversation not found')
        return row

    def create_conversation(self, user_id):
        identifier = str(uuid.uuid4());stamp = now()
        with self.engine.begin() as conn:
            conn.execute(insert(conversations).values(id=identifier,user_id=user_id,title='New study conversation',created_at=stamp,updated_at=stamp))
        return dict(id=identifier,title='New study conversation',created_at=iso(stamp),updated_at=iso(stamp))

    def list_conversations(self, user_id):
        with self.engine.connect() as conn:
            rows = conn.execute(select(conversations).where(conversations.c.user_id == user_id).order_by(conversations.c.updated_at.desc()).limit(30)).mappings()
            return [dict(id=r['id'],title=r['title'],created_at=iso(r['created_at']),updated_at=iso(r['updated_at'])) for r in rows]

    def conversation(self, user_id, identifier):
        with self.engine.connect() as conn:
            owner = self._owner(conn,user_id,identifier)
            rows = conn.execute(select(turns).where(turns.c.conversation_id == identifier).order_by(turns.c.id)).mappings()
            return dict(id=identifier,title=owner['title'],turns=[self._turn(r) for r in rows])

    def _turn(self, row):
        return dict(request_id=row['request_id'],question=row['question'],answer=row['answer'],
                    query=row['query'],sources=row['sources'],created_at=iso(row['created_at']))

    def lookup(self, user_id, identifier, request_id):
        with self.engine.connect() as conn:
            self._owner(conn,user_id,identifier)
            row = conn.execute(select(turns).where(turns.c.conversation_id == identifier,turns.c.request_id == request_id)).mappings().first()
            return self._turn(row) if row else None

    def save_turn(self, user_id, identifier, request_id, question, result):
        stamp = now()
        with self.engine.begin() as conn:
            self._owner(conn,user_id,identifier)
            conn.execute(insert(turns).values(conversation_id=identifier,request_id=request_id,question=question,
                answer=result['answer'],query=result['query'],sources=result['sources'],created_at=stamp))
            conn.execute(update(conversations).where(conversations.c.id == identifier).values(title=question[:120],updated_at=stamp))
        return self.lookup(user_id,identifier,request_id)
