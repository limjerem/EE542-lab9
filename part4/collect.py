"""Fetch pinned primary documents when rebuilding on another machine."""
import hashlib,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def collect(manifest,directory):
    directory.mkdir(parents=True,exist_ok=True)
    for source in manifest['sources']:
        path=directory/source['filename']
        if not path.exists():
            original=ROOT/'embedding/Ads cookbook .pdf'
            data=original.read_bytes() if source['id']=='cookbook' and original.exists() else httpx.get(source['url'],follow_redirects=True,timeout=90).raise_for_status().content
            if hashlib.sha256(data).hexdigest()!=source['sha256']:
                raise ValueError('Publisher document differs from pinned edition: '+source['title'])
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Document checksum mismatch: '+source['filename'])
