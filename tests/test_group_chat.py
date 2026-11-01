import asyncio
import importlib.util
from pathlib import Path
import sys
import threading
import numpy as np

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'groupchat_app_src/backend'))
from rag_service import RagReply


@pytest.fixture
def backend(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','sqlite+aiosqlite:///'+str(tmp_path/'chat.db'))
    monkeypatch.setenv('JWT_SECRET','local-unit-test-secret-value')
    spec=importlib.util.spec_from_file_location('chat_test_application',ROOT/'groupchat_app_src/backend/app.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import documents_api
    import lab9_core.kb as knowledge
    import knowledge_adapter
    monkeypatch.setattr(documents_api,'engine',module.engine)
    monkeypatch.setattr(documents_api,'Session',module.SessionLocal)
    state={'fail':False,'calls':0}
    def embedding(texts):
        state['calls']+=1
        if state['fail']:raise ConnectionError('injected embedding outage')
        return np.ones((len(texts),3),dtype=np.float32)
    monkeypatch.setattr(knowledge,'_kb',knowledge.KnowledgeBase(tmp_path/'knowledge',embedding))
    monkeypatch.setattr(knowledge_adapter,'cache_directory',lambda:tmp_path/'cache')
    module.upload_test_state=state
    class FakeRag:
        gate=threading.Event()
        histories=[]
        def load(self):return True
        def summary(self):return dict(topic='ADS',ready=True,indexed_chunks=2,documents=[])
        async def answer(self,question,history):
            self.histories.append((question,history))
            await asyncio.to_thread(self.gate.wait,3)
            if question.startswith('Fail'):raise ConnectionError('injected outage')
            return RagReply('Tuning is manual. [1]',[dict(label=1,filename='ADS.pdf',page=5,chunk_id='one',text='Tuning is manual.')],question)
    module.rag=FakeRag()
    with TestClient(module.app) as client:yield module,client


def account(client,name):
    response=client.post('/api/signup',json=dict(username=name,password='test-password-123'))
    assert response.status_code==200
    return response.json()['token']


def bot_message(socket):
    for _ in range(10):
        event=socket.receive_json()
        if event['type']=='message' and event['message']['is_bot']:return event['message']
    raise AssertionError('No bot message received')


def test_two_accounts_share_replies_and_sources_survive_reload(backend):
    module,client=backend
    first,second=account(client,'student_a'),account(client,'student_b')
    headers={'Authorization':'Bearer '+first}
    with client.websocket_connect('/ws') as one,client.websocket_connect('/ws') as two:
        one.send_json(dict(type='auth',token=first));two.send_json(dict(type='authenticate',token=second))
        assert one.receive_json()['type']=='connected' and two.receive_json()['type']=='ready'
        sent=client.post('/api/messages',headers=headers,json=dict(content='What is tuning?')).json()
        identifier=sent['message']['id']
        assert sent['bot_pending']
        assert identifier in client.get('/api/messages',headers=headers).json()['pending_replies']
        module.rag.gate.set()
        reply=bot_message(one)
        assert bot_message(two)['id']==reply['id']
        assert reply['reply_to']==identifier and reply['sources'][0]['page']==5
        persisted=client.get('/api/messages',headers={'Authorization':'Bearer '+second}).json()
        assert persisted['messages'][-1]['sources']==reply['sources']
        assert not persisted['pending_replies']
        assert client.get('/api/knowledge',headers=headers).json()['uploads_available'] is True


def test_history_uses_prior_reply_but_excludes_later_messages(backend):
    module,client=backend
    token=account(client,'student');headers={'Authorization':'Bearer '+token}
    with client.websocket_connect('/ws') as socket:
        socket.send_json(dict(type='auth',token=token));socket.receive_json()
        client.post('/api/messages',headers=headers,json=dict(content='First question?'))
        client.post('/api/messages',headers=headers,json=dict(content='Second question?'))
        client.post('/api/messages',headers=headers,json=dict(content='Future unrelated message'))
        module.rag.gate.set();bot_message(socket);bot_message(socket)
    history=module.rag.histories[1][1]
    assert any(m['role']=='assistant' for m in history)
    assert not any(m['content']=='Future unrelated message' for m in history)


def test_authentication_and_model_failure_are_explicit(backend):
    module,client=backend
    assert client.get('/api/messages').status_code==401
    assert client.get('/api/knowledge').status_code==401
    with client.websocket_connect('/ws') as socket:
        socket.send_json(dict(type='authenticate',token='invalid'))
        with pytest.raises(WebSocketDisconnect):socket.receive_json()
    token=account(client,'student');module.rag.gate.set()
    with client.websocket_connect('/ws') as socket:
        socket.send_json(dict(type='authenticate',token=token));socket.receive_json()
        client.post('/api/messages',headers={'Authorization':'Bearer '+token},json=dict(content='Fail this question?'))
        message=bot_message(socket)
        assert message['status']=='error' and message['sources']==[]


def test_merged_authentication_preserves_credential_validation(backend):
    module,client=backend
    for credentials in [dict(username='   ',password='test-password-123'),
                        dict(username='student',password='\u00e9'*40)]:
        assert client.post('/api/signup',json=credentials).status_code==422
    account(client,'existing_student')
    response=client.post('/api/login',json=dict(username=' existing_student ',password='test-password-123'))
    assert response.status_code==200
    assert module.verify_password('test-password-123','invalid-hash') is False
    with client.websocket_connect('/ws') as socket:
        socket.send_json(dict(type='message',token=response.json()['token']))
        with pytest.raises(WebSocketDisconnect) as error:socket.receive_json()
        assert error.value.code==4401


def test_real_upload_router_failure_retry_and_duplicate_use_shared_cache(backend):
    module,client=backend
    token=account(client,'uploader');headers={'Authorization':'Bearer '+token}
    module.upload_test_state['fail']=True
    upload=client.post('/api/documents',headers=headers,
                       files={'files':('sample.txt',b'ADS upload recovery regression.')}).json()['results'][0]
    assert upload['status']=='failed'
    module.upload_test_state['fail']=False
    retry=client.post(f"/api/documents/{upload['id']}/retry",headers=headers).json()
    assert retry['status']=='indexed'
    attempts=module.upload_test_state['calls']
    duplicate=client.post('/api/documents',headers=headers,
                          files={'files':('sample.txt',b'ADS upload recovery regression.')}).json()['results'][0]
    assert duplicate['result']=='duplicate' and module.upload_test_state['calls']==attempts
    rejected=client.post('/api/documents',headers=headers,
                         files={'files':('bad.docx',b'unsupported')}).json()['results'][0]
    assert rejected['result']=='rejected'
