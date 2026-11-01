"""
Bulk-load the curated folder into the knowledge base (same code path as the upload API).

    cd groupchat_app_src/backend
    python ingest_kb.py ../../data          # re-running is safe: duplicates are skipped
"""
import asyncio
import sys
from pathlib import Path

from fastapi import HTTPException

import documents_api as api


async def main(folder: str):
    await api.init_documents_db()
    files = sorted(p for p in Path(folder).rglob("*")
                   if p.suffix.lower() in api.SUPPORTED_EXTENSIONS)
    print(f"{len(files)} files in {folder}")
    counts = {}
    for f in files:
        try:
            r = await api.ingest_bytes(f.name, f.read_bytes())
            msg = f"{r['result']}: {r['pages']} pages, {r['chunks']} chunks"
            if r.get("error"):
                msg += f"  ERROR: {r['error']}"
        except HTTPException as exc:
            r, msg = {"result": "rejected"}, f"rejected: {exc.detail}"
        counts[r["result"]] = counts.get(r["result"], 0) + 1
        print(f"  {f.name}: {msg}")
    print("summary:", counts)
    await api.engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python ingest_kb.py <folder>")
    asyncio.run(main(sys.argv[1]))
