"""Native FAISS snapshots and a durable embedding cache; no pickle loading.

A generation becomes visible only when CURRENT is atomically replaced. Cached
vectors survive a failed publication, so a retry need not pay to embed them again.
Run one application writer process; callers serialize ingestion within that process.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
import threading
from contextlib import closing

import faiss
import numpy as np
from langchain_core.documents import Document

_PATH_LOCKS = {}
_REGISTRY_LOCK = threading.Lock()


class IndexSettingsError(ValueError):
    pass


class VectorStore:
    def __init__(self, directory, embeddings, settings, reuse_only=None):
        self.directory = Path(directory)
        self.embeddings = embeddings
        self.settings = settings
        self.reuse_only = reuse_only
        self.namespace = json.dumps(settings, sort_keys=True)
        self.index = None
        self.documents = []
        self.generation = None
        with _REGISTRY_LOCK:
            self._lock = _PATH_LOCKS.setdefault(str(self.directory.resolve()), threading.RLock())

    def _cache(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.directory / 'vectors.sqlite3')
        connection.execute('CREATE TABLE IF NOT EXISTS vectors '
                           '(namespace TEXT, digest TEXT, vector BLOB, '
                           'PRIMARY KEY(namespace, digest))')
        return connection

    @staticmethod
    def _digest(text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    @staticmethod
    def _matrix(vectors):
        matrix = np.ascontiguousarray(vectors, dtype=np.float32)
        if (matrix.ndim != 2 or not len(matrix) or not matrix.shape[1]
                or not np.isfinite(matrix).all()
                or (np.linalg.norm(matrix, axis=1) == 0).any()):
            raise ValueError('Invalid or empty embedding vectors')
        return matrix

    def seed_cache(self, native_directory):
        """Reuse the validated CLI vectors; require the same model and API origin."""
        path = Path(native_directory)
        payload = json.loads((path / 'chunks.json').read_text(encoding='utf-8'))
        if (self.settings.get('backend') != 'openai'
                or self.settings.get('model') != payload['embedding_model']
                or self.settings.get('api_base') != 'https://api.openai.com/v1'
                or payload.get('metric') != 'cosine'):
            raise ValueError('The supplied native index has incompatible embedding settings')
        index = faiss.read_index(str(path / 'index.faiss'))
        if index.d != payload['dimension'] or index.ntotal != len(payload['chunks']):
            raise ValueError('Native index and metadata do not match')
        vectors = self._matrix(index.reconstruct_n(0, index.ntotal))
        with closing(self._cache()) as connection, connection:
            connection.executemany('INSERT OR IGNORE INTO vectors VALUES (?, ?, ?)',
                [(self.namespace, self._digest(c['text']), v.tobytes())
                 for c, v in zip(payload['chunks'], vectors)])
        return len(vectors)

    def load(self):
        with self._lock:
            return self._load()

    def _load(self):
        pointer = self.directory / 'CURRENT'
        if not pointer.exists():
            self.index, self.documents, self.generation = None, [], None
            return False
        generation = pointer.read_text(encoding='utf-8').strip()
        if not generation or Path(generation).name != generation:
            raise ValueError('Invalid index generation')
        path = self.directory / generation
        payload = json.loads((path / 'chunks.json').read_text(encoding='utf-8'))
        if payload['settings'] != self.settings:
            raise IndexSettingsError('Index backend/model settings differ; use a separate index directory')
        index = faiss.read_index(str(path / 'index.faiss'))
        documents = [Document(page_content=d['text'], metadata=d['metadata'])
                     for d in payload['chunks']]
        if index.ntotal != len(documents) or index.d != payload['dimension']:
            raise ValueError('Index and metadata do not match')
        self.index, self.documents, self.generation = index, documents, generation
        return True

    def contains(self, chunk_ids):
        known = {d.metadata.get('chunk_id') for d in self.documents}
        return bool(chunk_ids) and set(chunk_ids).issubset(known)

    def _vectors(self, documents, cache=True):
        texts = [d.page_content for d in documents]
        if not cache:
            return self._matrix(self.embeddings.embed_documents(texts))
        with closing(self._cache()) as connection, connection:
            found = {}
            for text in texts:
                digest = self._digest(text)
                row = connection.execute('SELECT vector FROM vectors WHERE namespace=? AND digest=?',
                                         (self.namespace, digest)).fetchone()
                if row:
                    found[digest] = np.frombuffer(row[0], dtype=np.float32).copy()
            missing = list(dict.fromkeys(t for t in texts if self._digest(t) not in found))
            reuse_only = self.reuse_only if self.reuse_only is not None else os.getenv('RAG_REUSE_ONLY') == '1'
            if missing and reuse_only:
                raise ValueError('No cached vectors for this document; reuse-only mode blocks new document embeddings')
            for start in range(0, len(missing), 64):
                batch = missing[start:start + 64]
                vectors = self._matrix(self.embeddings.embed_documents(batch))
                if len(vectors) != len(batch):
                    raise ValueError('Embedding count differs from chunk count')
                for text, vector in zip(batch, vectors):
                    digest = self._digest(text)
                    found[digest] = vector
                    connection.execute('INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)',
                                       (self.namespace, digest, vector.tobytes()))
                connection.commit()  # retain each successful batch across later API failures
        return self._matrix([found[self._digest(t)] for t in texts])

    def replace_documents(self, documents, cache=True, extra_save=None):
        with self._lock:
            self._replace_documents(documents, cache, extra_save)

    def _replace_documents(self, documents, cache=True, extra_save=None):
        documents = list(documents)
        matrix = self._vectors(documents, cache=cache)
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        generation = 'gen-' + uuid.uuid4().hex
        path = self.directory / generation
        path.mkdir(parents=True)
        faiss.write_index(index, str(path / 'index.faiss'))
        (path / 'chunks.json').write_text(json.dumps({
            'settings': self.settings, 'dimension': index.d,
            'chunks': [{'text': d.page_content, 'metadata': d.metadata} for d in documents],
        }, ensure_ascii=False), encoding='utf-8')
        if extra_save:
            extra_save(path)
        pointer = self.directory / ('.CURRENT-' + uuid.uuid4().hex)
        pointer.write_text(generation)
        os.replace(pointer, self.directory / 'CURRENT')
        self.index, self.documents, self.generation = index, documents, generation

    def add_documents(self, documents):
        with self._lock:
            self.load()  # another Streamlit session may have published a generation
            known = {d.metadata['chunk_id'] for d in self.documents}
            fresh = []
            for document in documents:
                identifier = document.metadata['chunk_id']
                if identifier not in known:
                    fresh.append(document)
                    known.add(identifier)
            if fresh:
                self.replace_documents(self.documents + fresh)

    def similarity_search_with_score(self, query, k=4):
        # Keep the FAISS generation and its metadata together while a writer publishes.
        with self._lock:
            index, documents = self.index, self.documents
        if index is None:
            return []
        vector = self._matrix([self.embeddings.embed_query(query)])
        if vector.shape[1] != index.d:
            raise ValueError('Query vector dimension differs from the saved index')
        faiss.normalize_L2(vector)
        scores, indices = index.search(vector, min(k, index.ntotal))
        return [(documents[int(i)], float(s))
                for i, s in zip(indices[0], scores[0]) if i >= 0]

    def save_local(self, directory):
        if Path(directory).resolve() != self.directory.resolve():
            target = VectorStore(directory, self.embeddings, self.settings)
            # Copy exact vectors rather than making any further embedding requests.
            target.embeddings = _SavedEmbeddings(self.index.reconstruct_n(0, self.index.ntotal))
            target.replace_documents(self.documents, cache=False)


class _SavedEmbeddings:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed_documents(self, texts):
        return self.vectors
