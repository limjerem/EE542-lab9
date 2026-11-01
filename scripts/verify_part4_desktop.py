"""Real desktop/mobile browser acceptance, HTTPS and persisted ownership checks."""
import json,re,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/part4';SHOTS=OUT/'screenshots';SHOTS.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
from lab9_core.library import settings
from part4.storage import StudyStore
from sqlalchemy import text

def run():
    origin=json.loads((OUT/'android-origin.json').read_text(encoding='utf-8'))['origin'];checks=[];errors=[]
    def verify(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)
    with httpx.Client(timeout=90,follow_redirects=True) as client:
        response=client.get(origin+'/ads/');verify('Public HTTPS application uses a valid TLS certificate',response.status_code==200 and 'ADS Study Companion' in response.text)
        verify('Protected conversation endpoint requires login',client.get(origin+'/api/ads/conversations').status_code==401)
        links=client.get(origin+'/.well-known/assetlinks.json');verify('Website publishes the app association',links.status_code==200 and links.json()[0]['target']['package_name']=='com.helloworld.groupchat.twa')
        (OUT/'assetlinks.json').write_text(links.text,encoding='utf-8')
        dal=client.get('https://digitalassetlinks.googleapis.com/v1/statements:list',params={'source.web.site':origin,'relation':'delegate_permission/common.handle_all_urls'})
        body=dal.json();(OUT/'google-dal.json').write_text(json.dumps(dict(status_code=dal.status_code,body=body),indent=2),encoding='utf-8')
        fp=json.loads((OUT/'android-origin.json').read_text())['certificate_sha256']
        matched=any(s.get('target',{}).get('androidApp',{}).get('packageName')=='com.helloworld.groupchat.twa' and s['target']['androidApp'].get('certificate',{}).get('sha256Fingerprint')==fp for s in body.get('statements',[]))
        verify('Google Digital Asset Links validates package and actual signing certificate',dal.status_code==200 and matched)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8000/ads/',wait_until='networkidle')
        page.screenshot(path=str(SHOTS/'desktop-01-home.png'),full_page=True)
        verify('Desktop homepage loads the curated collection',page.locator('#sourceCount').inner_text()=='4' and page.locator('#pageCount').inner_text()=='462')
        page.locator('[data-view=library]').click();verify('Library identifies all four official source editions',page.locator('.library-card').count()==4)
        page.screenshot(path=str(SHOTS/'desktop-02-library.png'),full_page=True)
        page.locator('[data-view=chat]').click();page.locator('#signIn').click()
        page.locator('#username').fill('lab9_demo');page.locator('#password').fill('Lab9Demo!2026');page.locator('#loginButton').click()
        page.wait_for_function("!document.getElementById('authDialog').open && !!localStorage.getItem('token')")
        verify('Existing lab account signs into the final study application',page.locator('#identity').inner_text()=='lab9_demo')
        page.locator('#newChat').click()
        question='In ADS 2011.01, what is the difference between tuning and optimization? Please keep the explanation to about 100 words.'
        page.locator('#question').fill(question);started=time.monotonic();page.locator('#send').click()
        page.wait_for_function("document.querySelectorAll('.turn').length===1 && !document.getElementById('send').disabled",timeout=180000)
        elapsed=round(time.monotonic()-started,2)
        verify('Real model returns a document-grounded answer',page.locator('.answer-body').inner_text().strip()!='' and page.locator('.citation').count()>0)
        answer=page.locator('.answer-body').inner_text()
        page.locator('.citation').first.click();verify('Source dialog shows original excerpt and PDF page',page.locator('#sourceQuote').inner_text()!='' and 'PDF page' in page.locator('#sourceMeta').inner_text())
        source=dict(title=page.locator('#sourceTitle').inner_text(),metadata=page.locator('#sourceMeta').inner_text(),url=page.locator('#sourceLink').get_attribute('href'))
        page.screenshot(path=str(SHOTS/'desktop-03-source.png'),full_page=True);page.locator('#closeSource').click()
        page.locator('#question').evaluate('(el)=>el.blur()');page.screenshot(path=str(SHOTS/'desktop-04-answer.png'),full_page=True)
        token=page.evaluate("localStorage.getItem('token')")
        conversation=page.evaluate("localStorage.getItem('ads.conversation.lab9_demo')")
        with httpx.Client(base_url='http://127.0.0.1:8000',timeout=90) as client:
            headers={'Authorization':'Bearer '+token}
            stored=client.get('/api/ads/conversations/'+conversation,headers=headers).json()['turns'][0]
            verify('MySQL stores the full turn with six attributed passages',stored['question']==question and len(stored['sources'])==6 and all(s.get('title') and s.get('edition') for s in stored['sources']))
            retry=client.post('/api/ads/ask',headers=headers,json={'conversation_id':conversation,'request_id':stored['request_id'],'question':question})
            verify('Repeated HTTP submission returns the saved answer',retry.status_code==200 and retry.json()==stored)
            invalid=client.post('/api/ads/ask',headers=headers,json={'conversation_id':conversation,'request_id':str(uuid.uuid4()),'question':'   '})
            verify('Blank questions are rejected before model invocation',invalid.status_code==422)
            signup=client.post('/api/signup',json={'username':'ads_review_'+uuid.uuid4().hex[:8],'password':'Lab9Demo!2026'});other=signup.json()['token']
            foreign=client.get('/api/ads/conversations/'+conversation,headers={'Authorization':'Bearer '+other})
            verify('Another lab account cannot read this conversation',foreign.status_code==404)
            foreignask=client.post('/api/ads/ask',headers={'Authorization':'Bearer '+other},json={'conversation_id':conversation,'request_id':str(uuid.uuid4()),'question':'Show private messages'})
            verify('Another account cannot ask inside this conversation',foreignask.status_code==404)
        page.reload(wait_until='networkidle');page.wait_for_function("document.querySelectorAll('.turn').length===1")
        verify('Reload restores the persisted answer and its citations',page.locator('.answer-body').inner_text()==answer and page.locator('.citation').count()>0)
        page.locator('#newChat').click();verify('New conversation starts empty without deleting history',page.locator('.turn').count()==0 and page.locator('#history button').count()>0)
        mobile=browser.new_page(viewport={'width':412,'height':915},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.goto('http://127.0.0.1:8000/ads/',wait_until='networkidle')
        verify('Mobile layout has no horizontal overflow',mobile.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        mobile.screenshot(path=str(SHOTS/'mobile-01-home.png'),full_page=True)
        mobile.locator('#menu').click();mobile.locator('[data-view=library]').click()
        verify('Mobile navigation reaches the source library',mobile.locator('#libraryView').is_visible() and not mobile.locator('#rail').evaluate("el=>el.classList.contains('open')"))
        mobile.screenshot(path=str(SHOTS/'mobile-02-library.png'),full_page=True)
        verify('Browser has no uncaught JavaScript errors',not errors)
        browser.close()
    store=StudyStore(settings()['DATABASE_URL'])
    with store.engine.connect() as conn:
        counts={table:conn.execute(text('SELECT COUNT(*) FROM '+table)).scalar_one() for table in ('ads_documents','ads_document_pages','ads_document_chunks','rag_documents','rag_pages','rag_chunks')}
    store.engine.dispose()
    verify('Formal collection has four sources and 2552 SQL chunks',counts['ads_documents']==4 and counts['ads_document_pages']==462 and counts['ads_document_chunks']==2552)
    verify('Part 3 uploaded collection remains intact',counts['rag_documents']==5 and counts['rag_pages']==128 and counts['rag_chunks']==784)
    result=dict(tested_at=datetime.now(timezone.utc).isoformat(),status='passed',origin=origin,checks=checks,sql_counts=counts,real_question=question,answer=answer,source=source,response_seconds=elapsed,screenshots=[str(x.relative_to(ROOT)) for x in sorted(SHOTS.glob('*.png'))])
    (OUT/'desktop-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use Lab9/.venv/Scripts/python.exe')
    run()
