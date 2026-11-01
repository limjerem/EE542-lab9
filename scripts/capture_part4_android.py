"""Capture clean, unedited Android evidence after restarting the test browser."""
import asyncio,json,sys,subprocess,time
from pathlib import Path
import httpx
from websockets.asyncio.client import connect
from verify_part2_android import DevTools,ADB
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/part4';SHOTS=OUT/'screenshots'
def adb(*args):return subprocess.run([str(ADB),'-e',*args],capture_output=True,check=True)
async def main():
    url=json.loads((OUT/'android-origin.json').read_text())['launch_url']
    adb('shell','am','start','-n','com.helloworld.groupchat.twa/com.google.androidbrowserhelper.trusted.LauncherActivity')
    adb('forward','tcp:9224','localabstract:chrome_devtools_remote')
    async with httpx.AsyncClient(timeout=10) as client:
        tabs=[]
        for _ in range(30):
            try:tabs=[t for t in (await client.get('http://127.0.0.1:9224/json')).json() if t.get('url')==url]
            except httpx.TransportError:pass
            if tabs:break
            await asyncio.sleep(1)
    async with connect(tabs[0]['webSocketDebuggerUrl']) as ws:
        dev=DevTools(ws);assert await dev.until("document.querySelectorAll('.turn').length===2")
        await dev.js("document.activeElement.blur();document.getElementById('thread').scrollTop=document.getElementById('thread').scrollHeight;window.scrollTo(0,0);true")
        await asyncio.sleep(5)
        async def shot(name):
            await asyncio.sleep(.7);(SHOTS/(name+'.png')).write_bytes(adb('exec-out','screencap','-p').stdout);print('CAPTURED '+name,flush=True)
        await shot('android-08-clean-chat')
        await dev.js("document.querySelector('.turn:last-child .citation').click();document.activeElement.blur();true");await shot('android-09-clean-source')
        await dev.js("document.getElementById('closeSource').click();document.getElementById('menu').click();document.querySelector('[data-view=library]').click();document.activeElement.blur();true");await shot('android-10-clean-library')
        await dev.js("document.getElementById('libraryView').scrollTop=document.getElementById('libraryView').scrollHeight;true");await shot('android-11-clean-library-lower')
        await dev.js("document.getElementById('menu').click();document.getElementById('newChat').click();document.activeElement.blur();true");await shot('android-12-clean-home')
        await dev.js("document.getElementById('menu').click();document.getElementById('history').querySelectorAll('button')[1].click();document.activeElement.blur();true")
        assert await dev.until("document.querySelectorAll('.turn').length===2")
        await dev.js("document.activeElement.blur();document.getElementById('thread').scrollTop=document.getElementById('thread').scrollHeight;window.scrollTo(0,0);true")
        await shot('android-13-final')
        assert await dev.js("isSecureContext && matchMedia('(display-mode: standalone)').matches")
    report=json.loads((OUT/'android-verification.json').read_text(encoding='utf-8'));report['screenshots']=[str(x.relative_to(ROOT)) for x in sorted(SHOTS.glob('android-*.png'))]
    report['clean_capture_note']='Original adb PNG captures after restarting the lab browser; no password was saved, no image was edited, and no video was recorded.'
    (OUT/'android-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the project virtual environment')
    asyncio.run(main())
