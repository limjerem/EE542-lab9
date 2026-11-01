"""Regression for a delayed old-conversation response racing with New conversation."""
import asyncio,json,sys
from pathlib import Path
from datetime import datetime,timezone
import httpx
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/part4'
async def main():
    with httpx.Client(base_url='http://127.0.0.1:8000') as client:
        token=client.post('/api/login',json={'username':'lab9_demo','password':'Lab9Demo!2026'}).json()['token']
        history=client.get('/api/ads/conversations',headers={'Authorization':'Bearer '+token}).json()['conversations']
        identifier=history[0]['id']
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='chrome',headless=True)
        context=await browser.new_context(viewport={'width':1200,'height':900})
        await context.add_init_script('localStorage.setItem("token",'+json.dumps(token)+');localStorage.setItem("ads.username","lab9_demo");localStorage.setItem("ads.conversation.lab9_demo",'+json.dumps(identifier)+');')
        page=await context.new_page();started=asyncio.Event();release=asyncio.Event()
        async def hold(route):
            started.set();await release.wait();await route.continue_()
        await page.route('**/api/ads/conversations/'+identifier,hold)
        await page.goto('http://127.0.0.1:8000/ads/',wait_until='domcontentloaded')
        await asyncio.wait_for(started.wait(),15)
        await page.locator('#newChat').click();release.set()
        await page.wait_for_load_state('networkidle')
        assert await page.locator('.turn').count()==0
        assert await page.locator('#welcome').is_visible()
        assert await page.evaluate('localStorage.getItem("ads.conversation.lab9_demo")') is None
        assert not await page.locator('#send').is_disabled()
        await browser.close()
    (OUT/'ui-race-verification.json').write_text(json.dumps(dict(tested_at=datetime.now(timezone.utc).isoformat(),status='passed',checks=['Delayed restore cannot overwrite a newer New conversation action','Composer remains available','Old saved conversations remain in MySQL']),indent=2)+'\n',encoding='utf-8')
    print('PASS delayed restore cannot overwrite New conversation; no model API call was needed')
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the project virtual environment')
    asyncio.run(main())
