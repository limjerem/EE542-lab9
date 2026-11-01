"""Failure and budget regressions for the Part 3 persistence layer."""
from pathlib import Path
import sys

import numpy as np
import pytest
from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab9_core.vector_store import VectorStore, IndexSettingsError
from lab9_core import vector_store


class Embeddings:
    def __init__(self):
        self.batches = []
        self.fail_batch = None

    def embed_documents(self, texts):
        self.batches.append(list(texts))
        if len(self.batches) == self.fail_batch:
            raise ConnectionError('injected API outage')
        return [[1., 2., float(len(t)+1)] for t in texts]

    def embed_query(self, text):
        return [1., 2., 3.]


def document(i):
    return Document(page_content=f'ADS example {i}', metadata={'chunk_id':str(i),'source':'test.txt','page':1})


def test_failed_publication_preserves_previous_generation_and_cache(tmp_path, monkeypatch):
    embeddings = Embeddings()
    store = VectorStore(tmp_path, embeddings, {'backend':'test'})
    store.add_documents([document(0)])
    pointer = (tmp_path/'CURRENT').read_bytes()
    replace = vector_store.os.replace
    monkeypatch.setattr(vector_store.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.add_documents([document(1)])
    assert (tmp_path/'CURRENT').read_bytes() == pointer
    assert store.index.ntotal == 1
    monkeypatch.setattr(vector_store.os, 'replace', replace)
    reloaded = VectorStore(tmp_path, embeddings, {'backend':'test'})
    reloaded.load()
    reloaded.add_documents([document(1)])
    assert reloaded.index.ntotal == 2
    assert sum(map(len,embeddings.batches)) == 2
    reloaded.add_documents([document(1)])
    assert reloaded.index.ntotal == 2


def test_later_api_batch_failure_keeps_successful_batches(tmp_path):
    embeddings = Embeddings();embeddings.fail_batch = 2
    store = VectorStore(tmp_path, embeddings, {'backend':'test'})
    documents = [document(i) for i in range(70)]
    with pytest.raises(ConnectionError):
        store.add_documents(documents)
    assert not (tmp_path/'CURRENT').exists()
    embeddings.fail_batch = None
    store.add_documents(documents)
    assert [len(batch) for batch in embeddings.batches] == [64,6,6]
    assert store.index.ntotal == 70


def test_settings_mismatch_is_rejected(tmp_path):
    embeddings = Embeddings()
    VectorStore(tmp_path, embeddings, {'model':'one'}).add_documents([document(0)])
    with pytest.raises(IndexSettingsError):
        VectorStore(tmp_path, embeddings, {'model':'two'}).load()
    assert len(embeddings.batches) == 1


def test_zero_query_is_not_ranked_as_meaningful_retrieval(tmp_path):
    embeddings = Embeddings()
    store = VectorStore(tmp_path, embeddings, {'backend':'test'})
    store.add_documents([document(0)])
    embeddings.embed_query = lambda text: [0.,0.,0.]
    with pytest.raises(ValueError, match='Invalid'):
        store.similarity_search_with_score('unknown')
