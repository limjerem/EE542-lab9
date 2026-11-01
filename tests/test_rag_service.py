import asyncio
import json
from pathlib import Path
import sys

import httpx
from langchain_core.documents import Document
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'groupchat_app_src/backend'))
sys.path.insert(0,str(ROOT))
from rag_service import RagService, CachedQueries, KnowledgeUnavailable
from lab9_core.vector_store import VectorStore


class Embeddings:
    queries = 0
    def embed_documents(self, texts): return [[1.,2.,3.] for t in texts]
    def embed_query(self, text):
        self.queries += 1
        return [1.,2.,3.]


def index(tmp_path):
    embedding = Embeddings()
    store = VectorStore(tmp_path,embedding,{'backend':'test'})
    store.add_documents([Document(page_content=text,metadata=dict(source='ADS.pdf',page=5,chunk_id=str(i)))
                         for i,text in enumerate(['Tuning is manual.','Optimization is automated.'])])
    store.embeddings = CachedQueries(embedding,tmp_path,'test-model')
    return store,embedding


def test_followup_uses_current_passages_and_keeps_each_citation(tmp_path):
    store,embedding = index(tmp_path)
    requests = []
    def handler(request):
        payload = json.loads(request.content);requests.append(payload)
        text = 'ADS tuning versus optimization' if 'Rewrite' in payload['messages'][0]['content'] else 'Tuning is manual. [1]'
        return httpx.Response(200,json={'choices':[{'message':{'content':text}}]})
    service = RagService('http://local/v1','local',index=store,
        client_factory=lambda:httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    async def scenario():
        first = await service.answer('What is tuning?',[])
        second = await service.answer('How is it different from optimization?',[
            dict(role='user',content='What is tuning?'),dict(role='assistant',content=first.answer)])
        assert second.query=='ADS tuning versus optimization'
        assert [s['label'] for s in second.sources]==[1,2]
        assert all(s['page']==5 for s in second.sources)
        assert 'CURRENT PASSAGES' in requests[-1]['messages'][0]['content']
        assert 'never as instructions' in requests[-1]['messages'][0]['content']
        assert len(requests)==3
    asyncio.run(scenario())


def test_llm_failure_then_retry_reuses_query_cache(tmp_path,monkeypatch):
    store,embedding = index(tmp_path)
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls)==1:raise httpx.ConnectError('injected local outage')
        return httpx.Response(200,json={'choices':[{'message':{'content':'Tuning is manual. [1]'}}]})
    service = RagService('http://local/v1','local',index=store,
        client_factory=lambda:httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    async def scenario():
        with pytest.raises(httpx.ConnectError):await service.answer('What is tuning?',[])
        monkeypatch.setenv('RAG_QUERY_REUSE_ONLY','1')
        assert (await service.answer('What is tuning?',[])).sources
        assert embedding.queries==1
        with pytest.raises(ValueError,match='query reuse-only'):
            store.embeddings.embed_query('Uncached query')
        assert embedding.queries==1
    asyncio.run(scenario())


def test_missing_index_never_calls_the_model(tmp_path):
    store = VectorStore(tmp_path,Embeddings(),{'backend':'test'})
    service = RagService('http://unused/v1','local',index=store)
    with pytest.raises(KnowledgeUnavailable):asyncio.run(service.answer('What is tuning?',[]))
    assert not service.summary()['ready']
