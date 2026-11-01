"""Verify the installed Android wrapper through Chrome DevTools and real backend services.
Run only with backend/.venv/Scripts/python.exe. Test accounts/messages remain as lab evidence.
"""
import argparse, asyncio, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import asyncmy, httpx
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from websockets.asyncio.client import connect
ROOT=Path(__file__).resolve().parent.parent
ADB=Path.home()/'AppData/Local/Android/Sdk/platform-tools/adb.exe'
OUT=ROOT/'outputs/part2'
CHECKS=[]

def check(name, ok):
    CHECKS.append({'name':name,'passed':bool(ok)})
    print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok: raise AssertionError(name)

class DevTools:
    def __init__(self, socket): self.socket=socket;self.seq=0
    async def call(self, method, params=None):
        self.seq+=1; request_id=self.seq
        await self.socket.send(json.dumps({'id':request_id,'method':method,'params':params or {}}))
        while True:
            result=json.loads(await asyncio.wait_for(self.socket.recv(),timeout=30))
            if result.get('id')==request_id:
                if 'error' in result:raise RuntimeError(result['error'])
                return result.get('result',{})
    async def js(self, expression):
        result=await self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    async def until(self, expression, timeout=30):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if await self.js(expression):return True
            await asyncio.sleep(.4)
        return False

async def screenshot(label):
    await asyncio.sleep(.8)
    result=await asyncio.to_thread(subprocess.run,[str(ADB),'-e','exec-out','screencap','-p'],capture_output=True,check=True)
    path=OUT/'screenshots'/(label+'.png');path.parent.mkdir(parents=True,exist_ok=True)
    check('screenshot '+label,result.stdout.startswith(b'\x89PNG\r\n\x1a\n'))
    path.write_bytes(result.stdout)
    return str(path.relative_to(ROOT))

async def main(args):
    service_origin='http://127.0.0.1:8000' if args.origin=='http://10.0.2.2:8000' else args.origin
    stamp=datetime.now().strftime('%m%d_%H%M%S')
    username='twa_android_'+stamp;peer='twa_peer_'+stamp;password='Lab9Demo!2026'
    report={'tested_at':datetime.now(timezone.utc).isoformat(),'origin':args.origin,'mode':args.label,
            'android_username':username,'peer_username':peer,'checks':CHECKS,'screenshots':[],
            'test_data_retained':True,'twa_without_urlbar_verified':False}
    try:
        async with httpx.AsyncClient(timeout=150,limits=httpx.Limits(max_keepalive_connections=0)) as client:
            tabs=(await client.get('http://127.0.0.1:9224/json')).json()
            tabs=[t for t in tabs if t.get('type')=='page' and t.get('url','').rstrip('/')==args.origin.rstrip('/')]
            check('installed wrapper opened expected website',len(tabs)==1)
            asset=await client.get(service_origin+'/.well-known/assetlinks.json')
            check('assetlinks serves JSON without authentication',asset.status_code==200 and 'json' in asset.headers.get('content-type',''))
            expected=json.loads((ROOT/'groupchat_app_src/frontend/.well-known/assetlinks.json').read_text())
            check('served association matches APK package and certificate',asset.json()==expected)
            result=await client.post(service_origin+'/api/signup',json={'username':peer,'password':password})
            result.raise_for_status();peer_token=result.json()['token']
            async with connect(tabs[0]['webSocketDebuggerUrl'],max_size=4*1024*1024) as socket:
                dev=DevTools(socket)
                await dev.js("if(!document.getElementById('chat').classList.contains('hidden'))document.getElementById('logoutBtn').click();document.activeElement.blur();true")
                report['screenshots'].append(await screenshot(args.label+'-01-login'))
                await dev.js("document.getElementById('username').value="+json.dumps(username)+";document.getElementById('password').value="+json.dumps(password)+";document.getElementById('signupBtn').click();true")
                check('Android signup and authenticated WebSocket connect',await dev.until("document.getElementById('connectionStatus').textContent==='Connected' && !document.getElementById('chat').classList.contains('hidden')"))
                async with connect(service_origin.replace('https://','wss://').replace('http://','ws://')+'/ws') as observer:
                    await observer.send(json.dumps({'type':'authenticate','token':peer_token}))
                    check('second client authenticated',json.loads(await observer.recv()).get('type')=='ready')
                    message='Part 2: Android emulator sends a realtime group message.'
                    await dev.js("document.getElementById('chatInput').value="+json.dumps(message)+";document.getElementById('sendBtn').click();document.activeElement.blur();true")
                    event=json.loads(await asyncio.wait_for(observer.recv(),timeout=20))
                    first=event.get('message',{})
                    check('Android message reaches second client in realtime',event.get('type')=='message' and first.get('content')==message and first.get('username')==username)
                    peer_message='Part 2: Desktop peer message received on Android through WebSocket.'
                    result=await client.post(service_origin+'/api/messages',headers={'Authorization':'Bearer '+peer_token},json={'content':peer_message})
                    result.raise_for_status()
                    check('Android receives peer broadcast without reload',await dev.until("Array.from(document.querySelectorAll('.message-body')).some(n=>n.textContent==="+json.dumps(peer_message)+")"))
                    # Drain the observer's peer event before asking the real local Llama model.
                    await asyncio.wait_for(observer.recv(),timeout=10)
                    question='What is a Trusted Web Activity? Answer in one short sentence.'
                    await dev.js("document.getElementById('chatInput').value="+json.dumps(question)+";document.getElementById('sendBtn').click();document.activeElement.blur();true")
                    qevent=json.loads(await asyncio.wait_for(observer.recv(),timeout=20))
                    check('Android question broadcast',qevent.get('message',{}).get('content')==question)
                    bevent=json.loads(await asyncio.wait_for(observer.recv(),timeout=150));bot=bevent.get('message',{})
                    check('real Llama reply broadcast',bot.get('is_bot') and bool(bot.get('content','').strip()) and not bot['content'].startswith('Sorry, I could not reach'))
                    check('Android displays bot reply',await dev.until("Array.from(document.querySelectorAll('.message.bot .message-body')).some(n=>n.textContent==="+json.dumps(bot['content'])+")"))
                    await dev.until("!document.getElementById('sendBtn').disabled")
                    report['llm_question']=question;report['llm_reply']=bot['content']
                    report['message_ids']=[first['id'],qevent['message']['id'],bot['id']]
                    await dev.js("document.activeElement.blur();document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight;window.scrollTo(0,0);true")
                    report['screenshots'].append(await screenshot(args.label+'-02-realtime-llm'))
                    await dev.call('Page.reload')
                    check('login and chat connection survive reload',await dev.until("document.getElementById('connectionStatus')?.textContent==='Connected' && !document.getElementById('chat').classList.contains('hidden')"))
                    check('history and Llama answer restored',await dev.until("Array.from(document.querySelectorAll('.message.bot .message-body')).some(n=>n.textContent==="+json.dumps(bot['content'])+")"))
                    await dev.js("document.activeElement.blur();document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight;window.scrollTo(0,0);true")
                    report['screenshots'].append(await screenshot(args.label+'-03-history-restored'))
                config=dotenv_values(ROOT/'groupchat_app_src/.env');db=make_url(config['DATABASE_URL'])
                conn=await asyncmy.connect(host=db.host,port=db.port or 3306,user=db.username,password=db.password,db=db.database,charset='utf8mb4')
                try:
                    async with conn.cursor() as cursor:
                        ids=report['message_ids']
                        await cursor.execute('SELECT id,content,is_bot FROM messages WHERE id IN (%s,%s,%s)',tuple(ids))
                        rows=await cursor.fetchall()
                        check('Android messages and bot reply persisted in MySQL',len(rows)==3 and any(r[0]==bot['id'] and r[1]==bot['content'] and r[2] for r in rows))
                finally:conn.close()
                report['browser_page']=await dev.js("({title:document.title,origin:location.origin,secureContext:window.isSecureContext,connection:document.getElementById('connectionStatus').textContent,messageCount:document.querySelectorAll('.message').length})")
                report['status']='functional_checks_passed'
    except Exception as error:
        report['status']='failed';report['error']=str(error);raise
    finally:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/(args.label+'-verification.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the backend virtual environment')
    parser=argparse.ArgumentParser();parser.add_argument('--origin',required=True);parser.add_argument('--label',default='android-local')
    asyncio.run(main(parser.parse_args()))
