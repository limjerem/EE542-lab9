"""Live browser acceptance against the teammate Streamlit application."""
from pathlib import Path
from datetime import datetime,timezone
import json,re
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'outputs/part3';SHOTS=OUT/'screenshots';SHOTS.mkdir(parents=True,exist_ok=True)
report={'tested_at':datetime.now(timezone.utc).isoformat(),'url':'http://127.0.0.1:8501','browser':'Google Chrome','real_openai':True,'checks':[],'turns':[]}
def check(name,ok):
    report['checks'].append({'name':name,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok:raise AssertionError(name)
with sync_playwright() as runner:
    browser=runner.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    try:
        page.goto(report['url']);expect(page.get_by_text('ADS Document Assistant',exact=True)).to_be_visible()
        page.get_by_role('button',name='Load saved index',exact=True).click()
        expect(page.get_by_text('Saved index loaded.',exact=True)).to_be_visible(timeout=30000)
        page.screenshot(path=str(SHOTS/'01-upload-library.png'),full_page=True)
        messages=page.get_by_test_id('stChatMessage')
        questions=['According to the ADS cookbook, how does tuning differ from optimization?','Which one is automated, and which one is manual?']
        for number,question in enumerate(questions,1):
            page.get_by_placeholder('Ask about your documents').fill(question)
            page.get_by_placeholder('Ask about your documents').press('Enter')
            expect(messages).to_have_count(number*2,timeout=180000)
            answer=messages.nth(number*2-1).get_by_test_id('stMarkdownContainer').first.inner_text()
            check('browser answer '+str(number)+' cites document evidence',bool(re.search(r'\[\d+\]',answer)))
            expect(page.get_by_test_id('stExpander')).to_have_count(number)
            report['turns'].append({'question':question,'answer':answer})
            page.screenshot(path=str(SHOTS/f'0{number+1}-live-answer.png'),full_page=True)
        check('previous answer retains its retrieved source expander',page.get_by_test_id('stExpander').count()==2)
        page.get_by_test_id('stExpander').nth(1).locator('summary').click()
        expect(page.get_by_test_id('stExpander').nth(1).get_by_text(re.compile(r'\[1\].*PDF page'))).to_be_visible()
        page.screenshot(path=str(SHOTS/'04-followup-with-sources.png'),full_page=True)
        page.get_by_role('button',name='Clear conversation',exact=True).click()
        expect(messages).to_have_count(0);check('clear removes visible messages',messages.count()==0)
        page.screenshot(path=str(SHOTS/'05-conversation-cleared.png'),full_page=True)
        page.reload();page.get_by_role('button',name='Load saved index',exact=True).click()
        expect(page.get_by_text('Saved index loaded.',exact=True)).to_be_visible(timeout=30000)
        check('index remains available after browser reload',True)
        expect(page.get_by_test_id('stException')).to_have_count(0)
        report['status']='passed'
    except Exception as error:
        report['status']='failed';report['error_type']=type(error).__name__
        page.screenshot(path=str(SHOTS/'browser-failure.png'),full_page=True)
        (OUT/'browser-failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:
        (OUT/'live-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        browser.close()
