"""Regressions found while reviewing the teammate implementation on Windows."""
from pathlib import Path
from langchain_core.documents import Document
from lab9_core.vector_store import VectorStore

class Embeddings:
    def embed_documents(self,texts):return [[1.,float(len(t)),3.] for t in texts]
    def embed_query(self,text):return [1.,2.,3.]

def document(text,identifier):
    return Document(page_content=text,metadata={'chunk_id':identifier,'source':'课程资料.txt','page':1})

def test_search_keeps_matching_index_and_metadata_when_writer_publishes(tmp_path):
    store=VectorStore(tmp_path,Embeddings(),{'backend':'test'})
    old=document('Old retrieved passage','old')
    store.add_documents([old]);original=store.index
    class PublishDuringSearch:
        d=original.d
        ntotal=original.ntotal
        def search(self,*args):
            hits=original.search(*args)
            store.replace_documents([document('New unrelated passage','new')])
            return hits
    store.index=PublishDuringSearch()
    hits=store.similarity_search_with_score('question')
    assert hits[0][0].page_content==old.page_content
    assert store.documents[0].metadata['chunk_id']=='new'

def test_utf8_snapshot_survives_non_utf8_windows_default(tmp_path,monkeypatch):
    store=VectorStore(tmp_path,Embeddings(),{'backend':'test'})
    store.add_documents([document('中文资料和微波电路 μ','one')])
    read_text=Path.read_text
    def windows_read(self,*args,**kwargs):
        if 'encoding' not in kwargs:kwargs['encoding']='cp1252'
        return read_text(self,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',windows_read)
    reopened=VectorStore(tmp_path,Embeddings(),{'backend':'test'})
    reopened.load()
    assert reopened.documents[0].page_content=='中文资料和微波电路 μ'
    assert reopened.documents[0].metadata['source']=='课程资料.txt'


def test_upload_ui_keeps_retrieved_passages_for_previous_turns(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from lab9_core import library,conversation
    class Vectors:
        def load(self):return True
    class Database:
        def list_sources(self):return [('ADS.pdf',1)]
    class Collection:
        vectors=Vectors()
        database=Database()
    class Chat:
        def clear(self):pass
        def ask(self,question):
            return {'answer':'Supported answer [1]','sources':[{'filename':'ADS.pdf','page':1,'text':'Evidence for '+question}]}
    monkeypatch.setattr(library,'open_library',lambda:Collection())
    monkeypatch.setattr(conversation,'open_chat',lambda vectors:Chat())
    app=AppTest.from_file(str(Path(__file__).parents[1]/'embedding/upload_app.py')).run()
    next(b for b in app.button if b.label=='Load saved index').click().run()
    app.chat_input[0].set_value('First question').run()
    assert len(app.expander)==1
    app.chat_input[0].set_value('Follow-up question').run()
    assert not app.exception
    assert len(app.expander)==2
    next(b for b in app.button if b.label=='Clear conversation').click().run()
    assert len(app.expander)==0


def test_reuse_only_from_local_settings_blocks_new_api_calls(tmp_path,monkeypatch):
    from lab9_core import library
    from langchain_openai import OpenAIEmbeddings
    monkeypatch.delenv('RAG_REUSE_ONLY',raising=False)
    monkeypatch.setattr(library,'settings',lambda:{'OPENAI_API_KEY':'unit-test-key','DATABASE_URL':'sqlite:///'+str(tmp_path/'docs.db'),'PART3_INDEX_DIR':str(tmp_path/'index'),'RAG_REUSE_ONLY':'1'})
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected API request')
    monkeypatch.setattr(OpenAIEmbeddings,'embed_documents',forbidden)
    collection=library.open_library()
    import pytest
    with pytest.raises(ValueError,match='reuse-only'):
        collection.ingest([library.SourceFile('new.txt',b'Uncached ADS document')])


def test_api_balance_error_is_actionable_without_leaking_provider_body():
    import httpx
    from openai import RateLimitError
    from lab9_core.errors import user_error
    secret='sk-unit-test-private-value'
    response=httpx.Response(429,request=httpx.Request('POST','https://api.openai.com/v1/embeddings'))
    error=RateLimitError('Provider body '+secret,response=response,body={'code':'credit_balance_exhausted','type':'insufficient_quota'})
    message=user_error(error)
    assert 'credits' in message.lower() and secret not in message
