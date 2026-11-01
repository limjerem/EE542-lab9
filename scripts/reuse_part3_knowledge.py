"""Reuse existing Part 3 text and vectors in the web upload knowledge base.

Run with the web process stopped. This migration never requests embeddings and
keeps the original rag_* tables and FAISS snapshots intact.
"""
import asyncio
import json
from pathlib import Path
import sys

import faiss
import numpy as np
from dotenv import load_dotenv,dotenv_values
from sqlalchemy import select,func

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'groupchat_app_src/backend'))
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'groupchat_app_src/.env')
load_dotenv(ROOT/'embedding/.env')
import documents_api as api
from lab9_core.database import sources as original_sources, chunks as original_chunks
from lab9_core.kb import get_kb


async def main():
    values=dotenv_values(ROOT/'embedding/.env.upload')
    directory=Path(values.get('PART3_INDEX_DIR') or ROOT/'embedding/upload_index')
    generation=(directory/'CURRENT').read_text().strip()
    payload=json.loads((directory/generation/'chunks.json').read_text())
    assert payload['settings']==dict(backend='openai',model='text-embedding-3-small',api_base='https://api.openai.com/v1')
    index=faiss.read_index(str(directory/generation/'index.faiss'))
    matrix=index.reconstruct_n(0,index.ntotal)
    positions={item['metadata']['chunk_id']:i for i,item in enumerate(payload['chunks'])}
    knowledge=get_kb()
    knowledge.embed_fn=lambda texts:(_ for _ in ()).throw(AssertionError('Embedding is prohibited during migration'))
    await api.init_documents_db()
    imported=[]
    async with api.Session() as session:
        originals=(await session.execute(select(original_sources).order_by(original_sources.c.id))).mappings().all()
    for original in originals:
        async with api.Session() as session:
            document=await session.scalar(select(api.KBDocument).where(api.KBDocument.sha256==original['sha256']))
            if document and document.status=='indexed' and knowledge.has_document(document.id):continue
            rows=(await session.execute(select(original_chunks.c.page_no,original_chunks.c.content)
                  .where(original_chunks.c.document_id==original['id']).order_by(original_chunks.c.chunk_index))).all()
            selected=[]
            for i,(page,content) in enumerate(rows):
                position=positions[f"{original['sha256']}:{i}"]
                assert payload['chunks'][position]['text']==content
                selected.append(position)
            if document is None:
                document=api.KBDocument(filename=original['filename'],sha256=original['sha256'],
                    status='processing',num_pages=original['num_pages'],num_chunks=len(rows),text=original['text'])
                session.add(document);await session.flush()
                session.add_all(api.KBChunk(document_id=document.id,page_no=p,chunk_index=i,content=c)
                                for i,(p,c) in enumerate(rows))
            await session.commit()
            identifier=document.id
        with knowledge.lock:
            knowledge._drop(identifier)
            vectors=np.ascontiguousarray(matrix[selected],dtype=np.float32)
            knowledge.vectors=vectors if not knowledge.vectors.size else np.vstack([knowledge.vectors,vectors])
            knowledge.meta.extend(dict(doc_id=identifier,source=original['filename'],page=p,chunk=i,text=c)
                                  for i,(p,c) in enumerate(rows))
            knowledge._save()
        async with api.Session() as session:
            document=await session.get(api.KBDocument,identifier)
            document.status,document.error='indexed',None
            await session.commit()
        imported.append(dict(filename=original['filename'],chunks=len(rows)))
    async with api.Session() as session:
        counts={table.__tablename__:await session.scalar(select(func.count()).select_from(table))
                for table in [api.KBDocument,api.KBChunk]}
    report=dict(imported=imported,counts=counts,vectors=len(knowledge.meta),dimension=knowledge.vectors.shape[1],embedding_requests=0)
    (ROOT/'results/part4/sync-migration.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    await api.engine.dispose()


if __name__=='__main__':asyncio.run(main())
