"""Unified lab website: existing group chat plus the final ADS learning application."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator
from groupchat_app_src.backend.app import app,current_user,User
from lab9_core.errors import user_error
from part4.service import open_service

ROOT=Path(__file__).resolve().parents[1]
_service=None
original_lifespan=app.router.lifespan_context

@asynccontextmanager
async def lifespan(application):
    global _service
    async with original_lifespan(application):
        _service=await asyncio.to_thread(open_service)
        yield
        _service.store.engine.dispose()
app.router.lifespan_context=lifespan
router=APIRouter(prefix='/api/ads')

class Question(BaseModel):
    conversation_id:UUID
    request_id:UUID
    question:str=Field(min_length=1,max_length=2000)
    @field_validator('question')
    @classmethod
    def trimmed(cls,value):
        if not value.strip():raise ValueError('Enter a question')
        return value.strip()

@router.get('/health')
def health():return {'status':'ok','app':'ADS Study Companion','ready':_service is not None}

@router.get('/library')
def library():return _service.library()

@router.get('/conversations')
def list_conversations(user:User=Depends(current_user)):
    return {'conversations':_service.store.list_conversations(user.id)}

@router.post('/conversations')
def create_conversation(user:User=Depends(current_user)):
    return _service.store.create_conversation(user.id)

@router.get('/conversations/{identifier}')
def conversation(identifier:UUID,user:User=Depends(current_user)):
    try:return _service.store.conversation(user.id,str(identifier))
    except KeyError:raise HTTPException(404,'Conversation not found') from None

@router.post('/ask')
async def ask(data:Question,user:User=Depends(current_user)):
    try:return await asyncio.to_thread(_service.ask,user.id,str(data.conversation_id),str(data.request_id),data.question)
    except KeyError:raise HTTPException(404,'Conversation not found') from None
    except PermissionError as error:raise HTTPException(429,str(error)) from None
    except ValueError as error:raise HTTPException(409,str(error)) from None
    except Exception as error:raise HTTPException(502,'The study assistant could not answer. '+user_error(error)) from None

app.include_router(router)
app.mount('/ads',StaticFiles(directory=ROOT/'part4/web',html=True),name='ads')
