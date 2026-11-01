"""Exercise the local upload interface with cached ADS documents only."""
import json
import os
from pathlib import Path
import re
import sys

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    fixtures = ROOT/'local_artifacts/part3-upload-fixtures'
    metadata = json.loads((ROOT/'embedding/index_data/chunks.json').read_text())
    original = ROOT/'embedding'/metadata['sources'][0]['filename']
    report = dict(browser='Chromium',url='http://127.0.0.1:8501',checks=[],questions_submitted=0)
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True,channel=os.getenv('PLAYWRIGHT_BROWSER_CHANNEL') or None)
        page = browser.new_page(viewport={'width':1280,'height':960})
        try:
            def upload(paths, expected):
                page.goto(report['url'])
                page.locator('input[type=file]').set_input_files([str(p) for p in paths])
                button = page.get_by_role('button',name='Process',exact=True)
                expect(button).to_be_enabled()
                button.click()
                alert = page.get_by_text(re.compile(r'^Processed \d|^Processing failed'))
                expect(alert).to_be_visible(timeout=60000)
                assert expected in alert.inner_text(),alert.inner_text()
                expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            upload([original],'Processed 1 file(s): 771 chunks.')
            report['checks'].append('single_pdf')
            print('Single PDF passed.',flush=True)
            page.get_by_role('button',name='Process',exact=True).click()
            expect(page.get_by_text('Processed 1 file(s): 771 chunks.',exact=True)).to_be_visible(timeout=60000)
            report['checks'].append('repeat_process')
            upload([fixtures/'ADS_excerpt_page_5.pdf',fixtures/'ADS_excerpt_page_7.pdf'],
                   'Processed 2 file(s): 11 chunks.')
            report['checks'].append('multiple_pdf')
            print('Multiple PDFs passed.',flush=True)
            upload([fixtures/'ADS_excerpt.txt',fixtures/'ADS_excerpt.html'],
                   'Processed 2 file(s): 2 chunks.')
            report['checks'].append('text_and_html')
            page.reload()
            page.get_by_role('button',name='Load saved index',exact=True).click()
            expect(page.get_by_text('Saved index loaded.',exact=True)).to_be_visible(timeout=30000)
            report['checks'].append('reload_saved_index')
            page.get_by_role('button',name='Clear conversation',exact=True).click()
            report['checks'].append('clear_button')
            page.screenshot(path=str(ROOT/'results/upload-interface.png'),full_page=True)
        except Exception:
            page.screenshot(path=str(ROOT/'results/upload-failure.png'),full_page=True)
            (ROOT/'results/upload-failure.txt').write_text(page.locator('body').inner_text())
            raise
        finally:
            browser.close()
    (ROOT/'results/upload-ui.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
