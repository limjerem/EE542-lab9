"""Collect uploads, preserve source text, and publish cached retrieval vectors."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path

from dotenv import dotenv_values
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter

from lab9_core.database import Database
from lab9_core.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[1]
FILE_TYPES = ('pdf','txt','md','html','htm')


@dataclass(frozen=True)
class SourceFile:
    name: str
    data: bytes

    @classmethod
    def from_path(cls, path):
        path = Path(path).expanduser()
        return cls(path.name, path.read_bytes())

    @property
    def digest(self):
        return hashlib.sha256(self.data).hexdigest()

    def page_text(self):
        suffix = Path(self.name).suffix.lower().lstrip('.')
        if suffix not in FILE_TYPES:
            raise ValueError('Unsupported document type')
        if suffix == 'pdf':
            from pypdf import PdfReader
            return [(page.extract_text() or '').strip() for page in PdfReader(io.BytesIO(self.data)).pages]
        content = self.data.decode('utf-8')
        if suffix in ('html','htm'):
            from bs4 import BeautifulSoup
            document = BeautifulSoup(content,'html.parser')
            for element in document(['script','style','nav','header','footer']):
                element.decompose()
            content = document.get_text('\n')
        return [content.strip()]


def settings():
    values = {**dotenv_values(ROOT/'embedding/.env'),
              **dotenv_values(ROOT/'embedding/.env.upload'), **os.environ}
    return {key:value for key,value in values.items() if value is not None}


class DocumentLibrary:
    def __init__(self, database, vectors):
        self.database, self.vectors = database, vectors

    def ingest(self, files):
        splitter = CharacterTextSplitter(separator='\n', chunk_size=500, chunk_overlap=100)
        bounded = CharacterTextSplitter(separator='', chunk_size=500, chunk_overlap=100)
        documents, seen = [], set()
        # Share the index writer lock across extraction, SQL commits, and publication.
        with self.vectors._lock:
            for source in files:
                digest = source.digest
                if digest in seen:
                    continue
                seen.add(digest)
                page_text = source.page_text()
                selected = []
                for page,text in enumerate(page_text,1):
                    for section in splitter.split_text(text):
                        pieces = bounded.split_text(section) if len(section)>500 else [section]
                        for piece in pieces:
                            selected.append(Document(page_content=piece, metadata={
                                'source':source.name, 'page':page, 'sha256':digest,
                                'chunk_id':f'{digest}:{len(selected)}'}))
                if not selected:
                    raise ValueError(f'No extractable text in {source.name}')
                identifier = self.database.record(source.name,digest,page_text,selected)
                for item in selected:
                    item.metadata['doc_id'] = identifier
                documents.extend(selected)
            if not documents:
                raise ValueError('Select at least one nonempty document')
            self.vectors.add_documents(documents)
        return documents


def open_library():
    from langchain_openai import OpenAIEmbeddings
    values = settings()
    model = values.get('EMBEDDING_MODEL','text-embedding-3-small')
    embedding = OpenAIEmbeddings(model=model, api_key=values.get('OPENAI_API_KEY'))
    vectors = VectorStore(values.get('PART3_INDEX_DIR',ROOT/'embedding/upload_index'),embedding,
                         dict(backend='openai',model=model,api_base='https://api.openai.com/v1'),
                         reuse_only=values.get('RAG_REUSE_ONLY') == '1')
    vectors.load()
    if values.get('REUSE_NATIVE_INDEX'):
        vectors.seed_cache(values['REUSE_NATIVE_INDEX'])
    return DocumentLibrary(Database(values.get('DATABASE_URL','sqlite:///documents.db')),vectors)
