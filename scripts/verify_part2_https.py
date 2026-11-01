"""Refresh publicly verifiable HTTPS and Google Digital Asset Links evidence."""
import argparse,json,socket,ssl,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import httpx
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/part2'

def verify(origin):
    if not origin.startswith('https://'):raise ValueError('HTTPS origin required')
    expected=json.loads((ROOT/'groupchat_app_src/frontend/.well-known/assetlinks.json').read_text(encoding='utf-8-sig'))
    evidence={'tested_at':datetime.now(timezone.utc).isoformat(),'origin':origin,'provider':'localhost.run'}
    with httpx.Client(timeout=45,limits=httpx.Limits(max_keepalive_connections=0)) as client:
        home=client.get(origin+'/');home.raise_for_status()
        assert home.status_code==200 and 'Group Chat' in home.text and 'location' not in home.headers
        evidence['home']={'status':home.status_code,'is_lab9':True,'redirect':None}
        links=client.get(origin+'/.well-known/assetlinks.json');links.raise_for_status()
        assert links.status_code==200 and 'json' in links.headers.get('content-type','') and 'location' not in links.headers and links.json()==expected
        evidence['assetlinks']={'status':links.status_code,'content_type':links.headers.get('content-type'),'redirect':None,'body':links.json()}
        result=client.get('https://digitalassetlinks.googleapis.com/v1/statements:list',params={'source.web.site':origin,'relation':'delegate_permission/common.handle_all_urls'})
        result.raise_for_status();dal={'origin':origin,'http_status':result.status_code,'body':result.json()}
        target=expected[0]['target']
        assert any(s.get('target',{}).get('androidApp',{}).get('packageName')==target['package_name'] and s['target']['androidApp'].get('certificate',{}).get('sha256Fingerprint') in target['sha256_cert_fingerprints'] for s in dal.get('body',{}).get('statements',[])), 'Google DAL has not confirmed the certificate'
    context=ssl.create_default_context();hostname=urlsplit(origin).hostname
    with socket.create_connection((hostname,443),timeout=15) as tcp:
        with context.wrap_socket(tcp,server_hostname=hostname) as tls:
            cert=tls.getpeercert();evidence['tls']={'verified':True,'version':tls.version(),'subject':cert.get('subject'),'issuer':cert.get('issuer'),'not_before':cert.get('notBefore'),'not_after':cert.get('notAfter')}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('https-verification.json',evidence),('google-dal-statements.json',dal)]:
        (OUT/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('PASS public HTTPS, matching assetlinks, Google DAL and trusted TLS certificate',origin,flush=True)

if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the backend virtual environment')
    parser=argparse.ArgumentParser();parser.add_argument('--origin')
    args=parser.parse_args()
    origin=args.origin or json.loads((OUT/'origin-config.json').read_text(encoding='utf-8-sig'))['origin']
    verify(origin)
