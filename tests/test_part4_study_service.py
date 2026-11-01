"""Part 4 ownership, retry, memory and failed-turn persistence regressions."""
from copy import deepcopy
from uuid import uuid4
import pytest
from langchain_core.prompts import ChatPromptTemplate
from part4.storage import StudyStore
from part4.service import StudyService

def uid():return str(uuid4())

@pytest.fixture
def app(tmp_path):
    store=StudyStore('sqlite:///'+str(tmp_path/'study.sqlite3'))
    seen=[]
    class Chat:
        def __init__(self):
            self.history=[]
            self.answer=ChatPromptTemplate.from_messages([('system','Ground only in {context}')])
        def ask(self,question):
            seen.append([message.content for message in self.history])
            if question=='fail':raise RuntimeError('simulated unavailable model')
            return dict(answer='Answer [99]' if question=='invalid citation' else 'Supported answer [1]',query=question,
                sources=[dict(filename='manual.pdf',page=7,text='Supported passage',score=.8)])
    source=dict(id='manual',filename='manual.pdf',title='Official manual',edition='ADS 2011',url='https://example.org/manual.pdf',publisher='Publisher')
    service=StudyService(store,None,dict(sources=[source]),{},lambda _:Chat())
    yield service,store,seen
    store.engine.dispose()

def test_private_conversations_do_not_call_model(app):
    service,store,seen=app
    conv=store.create_conversation(1)['id']
    with pytest.raises(KeyError):service.ask(2,conv,uid(),'private question')
    with pytest.raises(KeyError):store.conversation(2,conv)
    assert store.list_conversations(2)==[] and seen==[]

def test_retry_returns_original_turn_without_second_model_call(app):
    service,store,seen=app;conv=store.create_conversation(1)['id'];request=uid()
    first=service.ask(1,conv,request,'How do I tune?')
    assert first==service.ask(1,conv,request,'How do I tune?')
    assert len(seen)==1 and len(store.conversation(1,conv)['turns'])==1
    with pytest.raises(ValueError):service.ask(1,conv,request,'Different question')
    assert len(seen)==1
    assert first['sources'][0]['edition']=='ADS 2011'

def test_only_successful_six_turns_restore_after_reopening(app):
    service,store,seen=app;conv=store.create_conversation(1)['id']
    for i in range(7):service.ask(1,conv,uid(),f'question {i}')
    assert seen[0]==[]
    assert len(seen[-1])==12 and seen[-1][0]=='question 0'
    service.ask(1,conv,uid(),'follow-up')
    assert len(seen[-1])==12 and seen[-1][0]=='question 1'
    assert len(store.conversation(1,conv)['turns'])==8

def test_failed_generation_and_invalid_citations_do_not_persist(app):
    service,store,seen=app;conv=store.create_conversation(1)['id']
    with pytest.raises(RuntimeError):service.ask(1,conv,uid(),'fail')
    with pytest.raises(ValueError):service.ask(1,conv,uid(),'invalid citation')
    assert store.conversation(1,conv)['turns']==[]
    service.ask(1,conv,uid(),'valid')
    assert seen[-1]==[]

def test_new_conversation_keeps_saved_history_but_starts_empty(app):
    service,store,seen=app;first=store.create_conversation(1)['id']
    service.ask(1,first,uid(),'old question')
    second=store.create_conversation(1)['id'];service.ask(1,second,uid(),'new question')
    assert seen[-1]==[] and len(store.conversation(1,first)['turns'])==1
    assert len(store.list_conversations(1))==2
