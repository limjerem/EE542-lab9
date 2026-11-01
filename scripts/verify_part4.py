"""Exercise B/C against the local MySQL, saved FAISS index and local Llama.

Only three public ADS/general questions use query embeddings. No document text is
embedded or sent to a cloud answer model. Uploads use the real shared backend.
"""
import json
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import time
from datetime import datetime, timezone

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/part4'
BASE='http://127.0.0.1:8000'


def cached_queries():
    path=ROOT/'embedding/upload_index/queries.sqlite3'
    if not path.exists():return 0
    with sqlite3.connect(path) as connection:
        return connection.execute('SELECT COUNT(*) FROM queries').fetchone()[0]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    identifier=secrets.token_hex(4)
    password=secrets.token_urlsafe(18)
    report=dict(checks=[],answers=[],upload_backend='real shared documents_api and knowledge base',
                document_embedding_requests=0,answer_provider='local Llama',query_cache_before=cached_queries(),
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                session_check='An intentionally invalid token exercises the 401/logout path; elapsed-time token expiration is not simulated.')
    with sync_playwright() as runner,httpx.Client(timeout=10) as client:
        browser=runner.chromium.launch(headless=True)
        contexts=[browser.new_context(viewport={'width':1380,'height':1000}) for _ in range(2)]
        pages=[context.new_page() for context in contexts]
        tokens=[]
        def send(page,content):
            page.locator('#chatInput').fill(content)
            with page.expect_response(lambda response: response.url==BASE+'/api/messages' and response.request.method=='POST') as response:
                page.locator('#chatInput').press('Enter')
            assert response.value.status==200
            return response.value.json()['message']['id']
        def wait_reply(request_id):
            deadline=time.monotonic()+150
            while time.monotonic()<deadline:
                response=client.get(BASE+'/api/messages',headers={'Authorization':'Bearer '+tokens[0]})
                response.raise_for_status()
                for message in response.json()['messages']:
                    if message.get('reply_to')==request_id:
                        assert message['status']=='ready',message['content']
                        return message
                pages[0].wait_for_timeout(250)
            raise AssertionError('Timed out waiting for the local answer')
        try:
            for index,page in enumerate(pages):
                page.goto(BASE)
                page.locator('#username').fill(f'bc_{identifier}_{index}')
                page.locator('#password').fill(password)
                page.get_by_role('button',name='Sign Up',exact=True).click()
                expect(page.locator('#chat')).to_be_visible(timeout=20000)
                expect(page.locator('#connectionStatus')).to_have_text('Connected',timeout=10000)
                tokens.append(page.evaluate("localStorage.getItem('token')"))
            report['checks'].append('two_account_signup_and_authenticated_websockets')
            credentials=dict(username=f'bc_{identifier}_0',password=password)
            (ROOT/'local_artifacts/part4/demo-account.json').write_text(json.dumps(credentials))
            knowledge=client.get(BASE+'/api/knowledge',headers={'Authorization':'Bearer '+tokens[0]}).json()
            assert knowledge['ready'] and knowledge['indexed_chunks']==784
            expect(pages[0].locator('#fileInput')).to_be_enabled()
            report['checks'].append('shared_knowledge_and_real_upload_router_available')
            headers={'Authorization':'Bearer '+tokens[0]}
            pages[0].locator('#fileInput').set_input_files(str(ROOT/'local_artifacts/part3-upload-fixtures/ADS_excerpt.txt'))
            pages[0].get_by_role('button',name='Upload documents',exact=True).click()
            expect(pages[0].locator('#uploadMsg')).to_contain_text('already indexed',timeout=30000)
            report['checks'].append('real_duplicate_upload')
            import html
            sample=(ROOT/'local_artifacts/part3-upload-fixtures/ADS_excerpt.txt').read_text()
            addition=ROOT/f'local_artifacts/part4/upload_{identifier}.html'
            addition.write_text('<article><p>'+html.escape(sample)+'</p></article>')
            pages[0].locator('#fileInput').set_input_files(str(addition))
            pages[0].get_by_role('button',name='Upload documents',exact=True).click()
            expect(pages[0].locator('#uploadMsg')).to_contain_text('1 chunks indexed',timeout=30000)
            documents=client.get(BASE+'/api/documents',headers=headers).json()['documents']
            created=next(d for d in documents if d['filename']==addition.name)
            assert created['status']=='indexed'
            assert client.get(BASE+'/api/knowledge',headers=headers).json()['indexed_chunks']==785
            retried=client.post(BASE+f"/api/documents/{created['id']}/retry",headers=headers).json()
            assert retried['status']=='indexed'
            assert client.get(BASE+'/api/knowledge',headers=headers).json()['indexed_chunks']==785
            report['checks'].extend(['real_new_upload_visible_to_chat_index','real_retry_does_not_duplicate_vectors'])
            probe=ROOT/f'local_artifacts/part4/uncached_{identifier}.txt'
            probe.write_text('Temporary uncached integration probe '+identifier)
            pages[0].locator('#fileInput').set_input_files(str(probe))
            pages[0].get_by_role('button',name='Upload documents',exact=True).click()
            expect(pages[0].locator('#uploadMsg')).to_contain_text('No cached vectors',timeout=30000)
            failed=pages[0].locator('#docList li').filter(has_text=probe.name)
            expect(failed).to_contain_text('failed')
            failed.get_by_role('button',name='Retry indexing',exact=True).click()
            expect(pages[0].locator('#uploadMsg')).to_contain_text('No cached vectors',timeout=30000)
            documents=client.get(BASE+'/api/documents',headers=headers).json()['documents']
            rejected=next(d for d in documents if d['filename']==probe.name)
            for item in (created,rejected):
                deletion=client.delete(BASE+f"/api/documents/{item['id']}",headers=headers)
                assert deletion.status_code==200
            assert client.get(BASE+'/api/knowledge',headers=headers).json()['indexed_chunks']==784
            pages[0].get_by_role('button',name='Refresh',exact=True).click()
            report['checks'].append('real_uncached_failure_visible_and_retryable_without_paid_embedding')
            report['checks'].append('delete_only_temporary_verification_documents')
            plain=f'Group chat check {identifier}'
            send(pages[0],plain)
            expect(pages[1].get_by_text(plain,exact=True)).to_be_visible(timeout=10000)
            report['checks'].append('plain_chat_broadcast')
            questions=['What is tuning used for in ADS?',
                       'How is it different from optimization?',
                       'How do I bake a chocolate cake?']
            replies=[]
            for i,question in enumerate(questions):
                request_id=send(pages[0 if i<2 else 1],question)
                message=wait_reply(request_id);replies.append(message)
                for page in pages:
                    expect(page.locator(f'[data-message-id="{message["id"]}"]')).to_be_visible(timeout=15000)
                assert message['sources']
                if i<2:assert re.search(r'\[\d+\]',message['content'])
                report['answers'].append(dict(question=question,answer=message['content'],
                    request_id=request_id,message_id=message['id'],
                    sources=[{k:v for k,v in source.items() if k!='text'} for source in message['sources']]))
                print(question+'\n'+message['content'],flush=True)
            assert 'tun' in replies[0]['content'].lower()
            assert 'optim' in replies[1]['content'].lower()
            assert re.search(r'not|enough|insufficient|cannot|can.t|don.t',replies[2]['content'],re.I)
            report['checks'].extend(['real_retrieval_and_local_answer','followup_with_shared_history','unsupported_question_refusal'])
            pages[0].reload()
            expect(pages[0].locator('#chat')).to_be_visible(timeout=15000)
            first=pages[0].locator(f'[data-message-id="{replies[0]["id"]}"]')
            expect(first.locator('details')).to_be_visible()
            first.locator('summary').click()
            expect(first.locator('.source-title').first).to_contain_text('PDF page')
            pages[0].screenshot(path=str(OUT/'chat-and-sources.png'),full_page=True)
            report['checks'].append('answer_sources_persist_after_reload')
            pages[0].evaluate('ws.close()')
            expect(pages[0].locator('#connectionStatus')).to_have_text('Reconnecting',timeout=5000)
            expect(pages[0].locator('#connectionStatus')).to_have_text('Connected',timeout=15000)
            report['checks'].append('websocket_reconnect')
            def reject_send(route):
                if route.request.method=='POST':route.fulfill(status=503,json={'detail':'Temporary test outage'})
                else:route.continue_()
            pages[0].route('**/api/messages',reject_send)
            pages[0].locator('#chatInput').fill('Preserve this unsent message')
            pages[0].get_by_role('button',name='Send',exact=True).click()
            expect(pages[0].locator('#chatError')).to_contain_text('Message not sent')
            expect(pages[0].locator('#chatInput')).to_have_value('Preserve this unsent message')
            pages[0].unroute('**/api/messages',reject_send)
            report['checks'].append('send_failure_preserves_input')
            malicious=f'<img data-check="{identifier}" src=x onerror="document.title=123">'
            send(pages[0],malicious)
            expect(pages[1].get_by_text(malicious,exact=True)).to_be_visible(timeout=10000)
            assert pages[1].locator('#messages img').count()==0
            report['checks'].append('message_text_is_not_html')
            pages[0].set_viewport_size({'width':390,'height':844})
            assert pages[0].evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            pages[0].screenshot(path=str(OUT/'mobile-layout.png'),full_page=True)
            report['checks'].append('responsive_web_layout')
            pages[1].get_by_role('button',name='Log Out',exact=True).click()
            expect(pages[1].locator('#auth')).to_be_visible()
            pages[1].evaluate("localStorage.setItem('token','invalid')")
            pages[1].reload()
            expect(pages[1].locator('#auth')).to_be_visible()
            expect(pages[1].locator('#authMsg')).not_to_be_empty()
            assert pages[1].evaluate("localStorage.getItem('token')") is None
            report['checks'].append('logout_and_invalid_session')
            report['query_cache_after']=cached_queries()
            report['new_query_vectors']=report['query_cache_after']-report['query_cache_before']
            (OUT/'verification.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
        except Exception:
            pages[0].screenshot(path=str(ROOT/'local_artifacts/part4/browser-failure.png'),full_page=True)
            (ROOT/'local_artifacts/part4/browser-failure.txt').write_text(pages[0].locator('body').inner_text())
            raise
        finally:browser.close()


if __name__=='__main__':main()
