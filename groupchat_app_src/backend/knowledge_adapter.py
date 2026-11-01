"""Bridge the upload knowledge base to existing vector caches and chat retrieval."""
from pathlib import Path
import os
import sys

from dotenv import dotenv_values
from langchain_core.documents import Document

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from lab9_core.kb import get_kb
from lab9_core.vector_store import VectorStore


def cache_directory():
    values=dotenv_values(ROOT/'embedding/.env.upload')
    return Path(os.getenv('RAG_QUERY_CACHE_DIR') or values.get('PART3_INDEX_DIR') or ROOT/'embedding/upload_index')


def shared_kb():
    knowledge=get_kb()
    with knowledge.lock:
        if not hasattr(knowledge,'_document_cache'):
            original=knowledge.embed_fn
            class Provider:
                def embed_documents(self,texts):return original(texts)
            cache=VectorStore(cache_directory(),Provider(),dict(backend='openai',
                model=os.getenv('EMBEDDING_MODEL','text-embedding-3-small'),
                api_base=os.getenv('EMBEDDING_API_BASE','https://api.openai.com/v1').rstrip('/')))
            knowledge._document_cache=cache
            knowledge.embed_fn=lambda texts:cache._vectors([Document(page_content=t) for t in texts])
    return knowledge


class ChatKnowledgeIndex:
    def __init__(self,embeddings):
        self.knowledge=shared_kb()
        self._lock=self.knowledge.lock
        self.embeddings=embeddings

    @property
    def documents(self):
        return [Document(page_content=m['text'],metadata=dict(source=m['source'],page=m['page'],
            doc_id=m['doc_id'],chunk_id=f"kb:{m['doc_id']}:{m['chunk']}")) for m in self.knowledge.meta]

    def load(self):
        with self._lock:
            self.knowledge._load()
            return bool(self.knowledge.meta)

    def similarity_search_with_score(self,query,k=4):
        import numpy as np
        with self._lock:
            if not self.knowledge.meta:return []
            vector=np.asarray(self.embeddings.embed_query(query),dtype=np.float32)
            if vector.shape!=(self.knowledge.vectors.shape[1],) or not np.isfinite(vector).all() or not np.linalg.norm(vector):
                raise ValueError('Invalid query vector for the knowledge base')
            scores=self.knowledge.vectors@(vector/np.linalg.norm(vector))
            documents=self.documents
            return [(documents[int(i)],float(scores[i])) for i in np.argsort(-scores)[:k]]
