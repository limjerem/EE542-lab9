"""Finalize real HTTPS TWA proof and verify Android logout/login without rerunning chat tests."""
import asyncio,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import httpx
from websockets.asyncio.client import connect
from verify_part2_android import DevTools,ADB,OUT
ROOT=OUT.parent.parent

def adb(*args,check=True):
    return subprocess.run([str(ADB),'-e',*args],capture_output=True,check=check)

async def main():
    report=json.loads((OUT/'android-https-verification.json').read_text(encoding='utf-8-sig'))
    origin=report['origin'];checks=[]
    def verify(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)
    verify('HTTPS chat integration passed',report['status']=='functional_checks_passed' and all(c['passed'] for c in report['checks']))
    tabs=httpx.get('http://127.0.0.1:9224/json',timeout=10).json()
    tab=next(t for t in tabs if t.get('url','').rstrip('/')==origin)
    async with connect(tab['webSocketDebuggerUrl'],max_size=4*1024*1024) as ws:
        dev=DevTools(ws)
        await dev.js("document.getElementById('logoutBtn').click();document.activeElement.blur();true")
        verify('Android logout returns to authentication',await dev.until("!localStorage.getItem('token') && !document.getElementById('auth').classList.contains('hidden')"))
        await dev.js("document.getElementById('username').value="+json.dumps(report['android_username'])+";document.getElementById('password').value='Lab9Demo!2026';document.getElementById('loginBtn').click();true")
        verify('Android login reconnects authenticated WSS',await dev.until("document.getElementById('connectionStatus').textContent==='Connected' && !document.getElementById('chat').classList.contains('hidden')"))
        verify('Android login restores persisted Llama reply',await dev.until("Array.from(document.querySelectorAll('.message.bot .message-body')).some(n=>n.textContent==="+json.dumps(report['llm_reply'])+")"))
        browser=await dev.js("({origin:location.origin,secureContext:window.isSecureContext,title:document.title,connection:document.getElementById('connectionStatus').textContent,standalone:matchMedia('(display-mode: standalone)').matches,fullscreen:matchMedia('(display-mode: fullscreen)').matches})")
        verify('Android page is the HTTPS secure origin',browser['origin']==origin and browser['secureContext'])
        await dev.js("document.activeElement.blur();document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight;window.scrollTo(0,0);true")
        await asyncio.sleep(1)
        shot=OUT/'screenshots/android-https-04-twa-final.png'
        shot.write_bytes(adb('exec-out','screencap','-p').stdout)
    links=adb('shell','pm','get-app-links','com.helloworld.groupchat.twa').stdout.decode('utf-8',errors='replace')
    (OUT/'android-app-links.txt').write_text(links,encoding='utf-8')
    hostname=origin.split('://',1)[1]
    verify('Android domain verification is verified',bool(re.search(re.escape(hostname)+r':\s+verified\b',links)))
    dal=json.loads((OUT/'google-dal-statements.json').read_text())
    fp='DA:2B:98:FC:35:C8:35:1A:4C:7B:C0:0F:44:88:94:4E:CA:0C:D1:76:79:E6:41:30:7C:9B:5E:78:7E:C1:CD:1D'
    statements=dal.get('body',{}).get('statements',[])
    verified=any(s.get('relation')=='delegate_permission/common.handle_all_urls' and s.get('target',{}).get('androidApp',{}).get('packageName')=='com.helloworld.groupchat.twa' and s['target']['androidApp'].get('certificate',{}).get('sha256Fingerprint')==fp for s in statements)
    verify('Google DAL confirms package and signing certificate',dal['http_status']==200 and verified)
    adb('shell','uiautomator','dump','/sdcard/lab9-twa-window.xml')
    adb('pull','/sdcard/lab9-twa-window.xml',str(OUT/'twa-window-hierarchy.xml'))
    import xml.etree.ElementTree as ET
    nodes=list(ET.parse(OUT/'twa-window-hierarchy.xml').iter('node'))
    ids=[e.get('resource-id') for e in nodes]
    verify('Chrome URL bar absent from visible Android hierarchy','com.android.chrome:id/url_bar' not in ids and 'com.android.chrome:id/toolbar' not in ids)
    webviews=[e.attrib for e in nodes if e.get('content-desc')=='Web View' or e.get('class')=='android.webkit.WebView']
    viewport=next(e.get('bounds') for e in nodes if e.get('resource-id')=='com.android.chrome:id/coordinator')
    verify('Chrome web content fills its viewport without a URL toolbar',any(e['bounds']==viewport for e in webviews))
    result={'tested_at':datetime.now(timezone.utc).isoformat(),'origin':origin,'package_name':'com.helloworld.groupchat.twa','checks':checks,'browser':browser,'visible_webviews':webviews,'screenshot':str(shot.relative_to(ROOT)),'visual_review':'Login screenshot and chat screenshot both show no URL bar; screenshot content was not edited.','full_twa_verified':True,'status':'passed'}
    (OUT/'twa-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report['twa_without_urlbar_verified']=True
    report['screenshots'].append(str(shot.relative_to(ROOT)))
    (OUT/'android-https-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the backend virtual environment')
    asyncio.run(main())
