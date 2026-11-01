"""The composed ADS application must import without a backend working directory."""
import os
from pathlib import Path
import subprocess
import sys


def test_root_entrypoint_keeps_shared_chat_upload_and_ads_routes():
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,DATABASE_URL='sqlite+aiosqlite:///:memory:',
             JWT_SECRET='isolated-root-import-test-secret',PYTHONDONTWRITEBYTECODE='1')
    code='''from part4.app import app
paths=set(app.openapi()['paths'])
assert {'/api/messages','/api/documents','/api/ads/health'} <= paths
assert any(getattr(route,'path',None)=='/ads' for route in app.routes)
print('root entrypoint routes ready')
'''
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=root,env=env,
                          capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stderr
    assert 'root entrypoint routes ready' in result.stdout
