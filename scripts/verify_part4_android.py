"""Installed ADS Android TWA acceptance with real questions and original screenshots."""
import asyncio,json,re,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import httpx
from websockets.asyncio.client import connect
from verify_part2_android import DevTools,ADB
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/part4';SHOTS=OUT/'screenshots'
def adb(*args,check=True):return subprocess.run([str(ADB),'-e',*args],capture_output=True,check=check)

async def main():
    config=json.loads((OUT/'android-origin.json').read_text());origin=config['origin'];url=config['launch_url'];checks=[];questions=[]
    def verify(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)
    async def shot(name):
        await asyncio.sleep(.6);path=SHOTS/(name+'.png');data=adb('exec-out','screencap','-p').stdout
        verify('Original Android screenshot: '+name,data.startswith(b'\x89PNG\r\n\x1a\n'));path.write_bytes(data)
    verify('Existing emulator booted',adb('shell','getprop','sys.boot_completed').stdout.strip()==b'1')
    package=adb('shell','dumpsys','package',config['package_name']).stdout.decode(errors='replace')
    verify('Installed APK is version 2.0',bool(re.search(r'versionCode=2\b',package)) and 'versionName=2.0' in package)
    flags=adb('shell','cat','/data/local/tmp/chrome-command-line',check=False)
    verify('No Chrome command-line trust bypass is installed',flags.returncode!=0)
    adb('forward','tcp:9224','localabstract:chrome_devtools_remote')
    async with httpx.AsyncClient(timeout=30) as client:
        candidates=[]
        for _ in range(45):
            try:
                tabs=(await client.get('http://127.0.0.1:9224/json')).json();candidates=[t for t in tabs if t.get('type')=='page' and t.get('url')==url]
            except httpx.TransportError:
                await asyncio.sleep(1);continue
            if candidates:break
            await asyncio.sleep(1)
        verify('Installed launcher opens the exact HTTPS ADS path',len(candidates)==1)
        async with connect(candidates[0]['webSocketDebuggerUrl'],max_size=4*1024*1024) as ws:
            dev=DevTools(ws)
            verify('ADS website has loaded on Android',await dev.until("!!document.getElementById('question') && document.getElementById('sourceCount').textContent==='4'"))
            await dev.js("if(localStorage.getItem('token'))document.getElementById('logout').click();document.activeElement.blur();true")
            await shot('android-01-home')
            await dev.js("document.getElementById('signIn').click();document.getElementById('username').value='lab9_demo';document.getElementById('password').value='Lab9Demo!2026';document.getElementById('loginButton').click();true")
            verify('Android login uses the existing lab account',await dev.until("!!localStorage.getItem('token') && !document.getElementById('authDialog').open"))
            await dev.js("document.getElementById('newChat').click();document.activeElement.blur();true")
            async def ask(question,count,name):
                await dev.js("document.getElementById('question').value="+json.dumps(question)+";document.getElementById('send').click();document.activeElement.blur();true")
                ok=await dev.until("document.querySelectorAll('.turn').length==="+str(count)+" && !document.getElementById('send').disabled",timeout=180)
                if not ok:print('ANDROID_NOTICE',await dev.js("document.getElementById('notice').textContent"),flush=True)
                verify(name,ok)
                answer=await dev.js("Array.from(document.querySelectorAll('.answer-body')).at(-1).innerText")
                questions.append(dict(question=question,answer=answer))
                return answer
            first=await ask('In the ADS 2011.01 S-Parameter Simulation manual, how do I define a frequency sweep using Start, Stop and Step? Answer in about 80 words.',1,'Android receives a real S-parameter answer')
            verify('Android answer exposes clickable source citations',await dev.js("document.querySelectorAll('.turn:last-child .citation').length>0"))
            await shot('android-02-sparameter-answer')
            await dev.js("document.querySelector('.turn:last-child .citation').click();document.activeElement.blur();true")
            verify('Android opens original excerpt, edition and page',await dev.until("document.getElementById('sourceDialog').open && document.getElementById('sourceQuote').textContent.length>0 && document.getElementById('sourceLink').href.includes('#page=')"))
            await shot('android-03-source');await dev.js("document.getElementById('closeSource').click();true")
            second=await ask('如果我想改用对数扫频，该改哪些设置？请用不超过100个中文字说明。',2,'Android Chinese follow-up resolves the previous sweep topic')
            verify('Follow-up answers in Chinese',bool(re.search(r'[\u4e00-\u9fff]',second)))
            await shot('android-04-chinese-followup')
            token=await dev.js("localStorage.getItem('token')");conversation=await dev.js("localStorage.getItem('ads.conversation.lab9_demo')")
            stored=(await client.get(origin+'/api/ads/conversations/'+conversation,headers={'Authorization':'Bearer '+token})).json()
            verify('Follow-up query is rewritten using conversation history',stored['turns'][-1]['query']!=questions[-1]['question'] and bool(re.search('ADS.*2011',stored['turns'][-1]['query'],re.I)) and bool(re.search('sweep|frequency|S.?parameter|扫频|频率',stored['turns'][-1]['query'],re.I)))
            verify('New official S-parameter manual participates in retrieval',any(s['source_id']=='sparameters' for turn in stored['turns'] for s in turn['sources']))
            await dev.call('Page.reload')
            verify('Android reload restores both turns and their references',await dev.until("document.querySelectorAll('.turn').length===2 && document.querySelectorAll('.citation').length>0"))
            await dev.js("document.getElementById('newChat').click();document.activeElement.blur();true")
            verify('Android new chat is empty and prior history remains selectable',await dev.js("document.querySelectorAll('.turn').length===0 && document.querySelectorAll('#history button').length>0"))
            limited=await ask('Give the exact menu path for the new AI design assistant in ADS 2026. Do these ADS 2011 manuals verify that path? Answer in at most 60 words.',1,'Android tests the collection version boundary')
            verify('Assistant acknowledges that the 2011 collection cannot verify ADS 2026',bool(re.search('2011',limited)) and bool(re.search(r'cannot|can.t|do not|not provide|not verify|not cover|does not|not contain|unable|don.t',limited,re.I)))
            await shot('android-05-version-boundary')
            await dev.js("document.getElementById('menu').click();document.querySelector('[data-view=library]').click();document.activeElement.blur();true")
            verify('Android source library displays all four manuals',await dev.js("!document.getElementById('libraryView').classList.contains('hidden') && document.querySelectorAll('.library-card').length===4"))
            await shot('android-06-library')
            await dev.js("document.getElementById('menu').click();document.getElementById('history').querySelectorAll('button')[1].click();document.activeElement.blur();true")
            verify('Android can reopen the saved technical conversation',await dev.until("document.querySelectorAll('.turn').length===2"))
            await shot('android-07-final-study-chat')
            browser=await dev.js("({url:location.href,secureContext:isSecureContext,standalone:matchMedia('(display-mode: standalone)').matches,horizontalOverflow:document.documentElement.scrollWidth>innerWidth,title:document.title})")
            verify('Android has a secure standalone display and no horizontal overflow',browser['secureContext'] and browser['standalone'] and not browser['horizontalOverflow'])
    links=adb('shell','pm','get-app-links',config['package_name']).stdout.decode(errors='replace');(OUT/'android-app-links.txt').write_text(links,encoding='utf-8')
    verify('Android verifies the app link domain',bool(re.search(re.escape(origin.split('://')[1])+r':\s+verified\b',links)))
    adb('shell','uiautomator','dump','/sdcard/lab9-part4-window.xml');adb('pull','/sdcard/lab9-part4-window.xml',str(OUT/'android-window.xml'))
    import xml.etree.ElementTree as ET
    nodes=list(ET.parse(OUT/'android-window.xml').iter('node'));ids=[n.get('resource-id') for n in nodes]
    verify('Visible Android hierarchy has no Chrome URL bar or toolbar','com.android.chrome:id/url_bar' not in ids and 'com.android.chrome:id/toolbar' not in ids)
    viewport=next(n.get('bounds') for n in nodes if n.get('resource-id')=='com.android.chrome:id/coordinator')
    verify('Trusted web content fills the browser viewport',any(n.get('bounds')==viewport for n in nodes if n.get('class')=='android.webkit.WebView' or n.get('content-desc')=='Web View'))
    report=dict(tested_at=datetime.now(timezone.utc).isoformat(),status='passed',origin=origin,checks=checks,browser=browser,real_questions=questions,followup_retrieval_query=stored['turns'][-1]['query'],source_ids=sorted({s['source_id'] for t in stored['turns'] for s in t['sources']}),full_twa_verified=True,screenshots=[str(x.relative_to(ROOT)) for x in sorted(SHOTS.glob('android-*.png'))])
    (OUT/'android-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use Lab9/.venv/Scripts/python.exe')
    asyncio.run(main())
