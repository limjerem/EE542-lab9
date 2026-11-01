"""ADS Study Companion: reuse the Part 3 grounded conversation implementation."""
from pathlib import Path
import json, re, threading, time
from collections import defaultdict, deque
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from lab9_core.library import settings
from lab9_core.vector_store import VectorStore
from lab9_core.conversation import open_chat
from part4.storage import StudyStore

ROOT=Path(__file__).resolve().parents[1]
SCOPE='''You are ADS Study Companion for EE/RF engineering students. The collection covers ADS 2011 and 2011.01 workflows and Circuit Design Cookbook 2.0. Make the version clear when a procedure depends on the interface. Do not claim these manuals describe current ADS versions. Help with practical steps and explain terms. Acknowledge missing context instead of guessing. Answer in the language of the question.'''

class StudyService:
    def __init__(self, store, vectors, manifest, state, chat_factory=open_chat):
        self.store,self.vectors,self.manifest,self.state,self.chat_factory=store,vectors,manifest,state,chat_factory
        self._guard=threading.Lock();self._locks={};self._requests=defaultdict(deque);self._global=deque()
        self._sources={s['filename']:s for s in manifest['sources']}

    def library(self):
        return dict(name='ADS Study Companion',audience=self.manifest['audience'],scope=self.manifest['scope'],
            source_count=self.state['source_count'],pages=self.state['pages'],chunks=self.state['chunks'],
            sources=[{k:s[k] for k in ('id','title','filename','publisher','edition','url','pages','topic')} for s in self.manifest['sources']])

    def ask(self,user_id,identifier,request_id,question):
        with self._guard:lock=self._locks.setdefault(identifier,threading.Lock())
        with lock:
            previous=self.store.lookup(user_id,identifier,request_id)
            if previous:
                if previous['question']!=question:raise ValueError('Request identifier already used for a different question')
                return previous
            conversation=self.store.conversation(user_id,identifier)
            if len(conversation['turns'])>=50:raise ValueError('Start a new study conversation to continue')
            with self._guard:
                stamp=time.monotonic();recent=self._requests[user_id]
                for queue in (recent,self._global):
                    while queue and stamp-queue[0]>60:queue.popleft()
                if len(recent)>=10 or len(self._global)>=25:raise PermissionError('Please wait a minute before asking another question')
                recent.append(stamp);self._global.append(stamp)
            chat=self.chat_factory(self.vectors)
            # The teammate chain retains six successful turns. SQL remains the source of truth.
            for turn in conversation['turns'][-6:]:
                chat.history.extend([HumanMessage(content=turn['question']),AIMessage(content=turn['answer'])])
            original=chat.answer.messages[0].prompt.template
            chat.answer=ChatPromptTemplate.from_messages([('system',SCOPE+'\n\n'+original),MessagesPlaceholder('history'),('human','{question}')])
            result=chat.ask(question)
            for label in re.findall(r'\[(\d+)\]',result['answer']):
                if not 1<=int(label)<=len(result['sources']):raise ValueError('The answer could not be linked to its sources; please retry')
            for hit in result['sources']:
                source=self._sources[hit['filename']]
                hit.update(source_id=source['id'],title=source['title'],edition=source['edition'],url=source['url'],publisher=source['publisher'])
            return self.store.save_turn(user_id,identifier,request_id,question,result)


def open_service():
    from langchain_openai import OpenAIEmbeddings
    values=settings();directory=ROOT/'local_artifacts/part4'
    manifest=json.loads((ROOT/'part4/corpus.json').read_text(encoding='utf-8'))
    state=json.loads((directory/'corpus-state.json').read_text(encoding='utf-8'))
    model=values.get('EMBEDDING_MODEL','text-embedding-3-small')
    vectors=VectorStore(directory/'index',OpenAIEmbeddings(model=model,api_key=values.get('OPENAI_API_KEY')),
        dict(backend='openai',model=model,api_base='https://api.openai.com/v1'),reuse_only=True)
    if not vectors.load() or vectors.generation!=state['generation']:raise ValueError('Prepare the ADS knowledge base before starting the app')
    return StudyService(StudyStore(values['DATABASE_URL']),vectors,manifest,state)
