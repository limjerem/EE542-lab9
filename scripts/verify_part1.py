"""Exercise the real Part 1 services; remove only accounts/messages created by this run."""
import asyncio
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import asyncmy
import bcrypt
import httpx
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parent.parent
WEB = 'http://127.0.0.1:8000'
WS = 'ws://127.0.0.1:8000/ws'
CONFIG = dotenv_values(ROOT/'groupchat_app_src/.env')
CHECKS = []
USERS = []
BOT_IDS = []
ANSWERS = []

def check(name, condition):
    CHECKS.append({'name':name,'passed':bool(condition)})
    print(('PASS' if condition else 'FAIL'),name,flush=True)
    if not condition:
        raise AssertionError(name)

async def database():
    url = make_url(CONFIG['DATABASE_URL'])
    return await asyncmy.connect(host=url.host,port=url.port or 3306,user=url.username,
                                password=url.password,db=url.database,charset='utf8mb4',connect_timeout=10)

async def next_message(socket):
    while True:
        payload=json.loads(await asyncio.wait_for(socket.recv(),timeout=120))
        if payload.get('type')!='bot_status':break
    check('websocket message event',payload.get('type')=='message')
    message=payload['message']
    if message['is_bot'] and message['id'] not in BOT_IDS:
        BOT_IDS.append(message['id'])
    return message

async def main():
    stamp=secrets.token_hex(4)
    password=secrets.token_urlsafe(18)
    async with httpx.AsyncClient(base_url=WEB,timeout=150) as client:
        check('website loads',(await client.get('/')).status_code==200)
        check('CSS loads',(await client.get('/styles.css')).status_code==200)
        check('JavaScript loads',(await client.get('/app.js')).status_code==200)
        check('message history requires login',(await client.get('/api/messages')).status_code==401)
        check('posting requires login',(await client.post('/api/messages',json={'content':'unauthorized'})).status_code==401)
        check('invalid token rejected',(await client.get('/api/messages',headers={'Authorization':'Bearer invalid'})).status_code==401)
        for credentials in ({'username':'   ','password':password},
                            {'username':'valid_name','password':'short'},
                            {'username':'valid_name','password':'\u00e9'*40}):
            check('invalid credentials rejected',(await client.post('/api/signup',json=credentials)).status_code==422)
        tokens=[]
        for suffix in ('alice','bob'):
            username=f'lab9_check_{stamp}_{suffix}'
            USERS.append(username)
            response=await client.post('/api/signup',json={'username':username,'password':password})
            check('signup '+suffix,response.status_code==200)
            tokens.append(response.json()['token'])
        response=await client.post('/api/signup',json={'username':USERS[0],'password':password})
        check('duplicate username rejected',response.status_code==409)
        response=await client.post('/api/login',json={'username':USERS[0],'password':'wrong_password'})
        check('wrong password rejected',response.status_code==401)
        response=await client.post('/api/login',json={'username':USERS[0],'password':password})
        check('login succeeds',response.status_code==200)
        headers={'Authorization':'Bearer '+response.json()['token']}
        check('empty message rejected',(await client.post('/api/messages',headers=headers,json={'content':'   '})).status_code==400)
        check('oversize message rejected',(await client.post('/api/messages',headers=headers,json={'content':'x'*4001})).status_code==422)
        async with connect(WS) as unauthorized:
            await unauthorized.send(json.dumps({'type':'authenticate','token':'invalid'}))
            try:
                await asyncio.wait_for(unauthorized.recv(),timeout=10)
                check('unauthenticated websocket rejected',False)
            except ConnectionClosed as error:
                check('unauthenticated websocket rejected',error.rcvd is not None and error.rcvd.code==4401)
        async with connect(WS) as alice,connect(WS) as bob:
            for socket,token in zip((alice,bob),tokens):
                await socket.send(json.dumps({'type':'authenticate','token':token}))
                payload=json.loads(await asyncio.wait_for(socket.recv(),timeout=10))
                check('authenticated websocket ready',payload.get('type')=='ready')
            content=f'Part 1 realtime check {stamp}'
            response=await client.post('/api/messages',headers=headers,json={'content':content})
            check('ordinary message accepted',response.status_code==200)
            received=await asyncio.gather(next_message(alice),next_message(bob))
            check('two users receive same broadcast',received[0]==received[1] and received[0]['content']==content and not received[0]['is_bot'])
            knowledge=await client.get('/api/knowledge',headers=headers)
            document_mode=knowledge.status_code==200 and knowledge.json().get('ready',False)
            questions=('What is tuning used for in ADS?', 'How do I bake a chocolate cake?') if document_mode else (
                'What is 2 + 2? Reply with only the number.', 'Explain machine learning in one short sentence\uff1f')
            for question in questions:
                sending=asyncio.create_task(client.post('/api/messages',headers=headers,json={'content':question}))
                user_messages=await asyncio.gather(next_message(alice),next_message(bob))
                check('question broadcast to both users',user_messages[0]==user_messages[1] and user_messages[0]['content']==question)
                bot_messages=await asyncio.gather(next_message(alice),next_message(bob))
                response=await sending
                answer=bot_messages[0]
                check('LLM request succeeds',response.status_code==200)
                check('real Llama reply reaches both users',answer==bot_messages[1] and answer['is_bot'] and bool(answer['content'].strip()) and answer.get('status')!='error' and not answer['content'].startswith('Sorry, I could not reach'))
                if not document_mode and question.startswith('What'):
                    check('arithmetic answer correct','4' in answer['content'])
                if document_mode and question.startswith('What'):
                    check('document reply cites retrieved passages',bool(answer.get('sources')) and '[1]' in answer['content'])
                ANSWERS.append({'question':question,'answer':answer['content']})
                print('LLAMA_REPLY',answer['content'],flush=True)
            history=(await client.get('/api/messages',headers=headers)).json()['messages']
            check('history preserves normal message',any(m['content']==content for m in history))
            check('history preserves both bot replies',all(any(m['id']==i and m['is_bot'] for m in history) for i in BOT_IDS))
        conn=await database()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute('SELECT password_hash FROM users WHERE username=%s',(USERS[0],))
                hashed=(await cursor.fetchone())[0]
                check('password stored as bcrypt hash',hashed!=password and bcrypt.checkpw(password.encode(),hashed.encode()))
                await cursor.execute('SELECT COUNT(*) FROM messages WHERE content=%s',(content,))
                check('message committed to MySQL',(await cursor.fetchone())[0]==1)
        finally:
            conn.close()

async def cleanup():
    conn=await database()
    try:
        async with conn.cursor() as cursor:
            for name in USERS:
                await cursor.execute('DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE username=%s)',(name,))
                await cursor.execute('DELETE FROM users WHERE username=%s',(name,))
            for message_id in BOT_IDS:
                await cursor.execute('DELETE FROM messages WHERE id=%s AND is_bot=TRUE',(message_id,))
        await conn.commit()
        print('OWNED_TEST_DATA_CLEANED',flush=True)
    finally:
        conn.close()

async def run():
    result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'model':CONFIG.get('LLM_MODEL')}
    try:
        await main()
        result['status']='passed'
    except Exception as error:
        result['status']='failed'
        result['error']=f'{type(error).__name__}: {error}'
        raise
    finally:
        await cleanup()
        result.update(checks=CHECKS,answers=ANSWERS)
        output=ROOT/'work/part1-verification.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('REPORT',output,flush=True)

if __name__=='__main__':
    asyncio.run(run())
