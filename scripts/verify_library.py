"""Verify stored PDF text and cached vectors without external API requests."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab9_core.database import Database
from lab9_core.library import SourceFile, DocumentLibrary, settings
from lab9_core.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[1]


class NoNetworkEmbeddings:
    def embed_documents(self, texts):
        raise AssertionError('Unexpected document embedding request')
    def embed_query(self, text):
        raise AssertionError('Unexpected query embedding request')


def main():
    values = settings()
    native = Path(values['REUSE_NATIVE_INDEX'])
    payload = json.loads((native/'chunks.json').read_text())
    database = Database(values['DATABASE_URL'])
    store = VectorStore(values['PART3_INDEX_DIR'],NoNetworkEmbeddings(),
        dict(backend='openai',model=payload['embedding_model'],api_base='https://api.openai.com/v1'))
    store.load()
    before_vectors = store.index.ntotal
    before_rows = database.counts()
    store.seed_cache(native)
    source = ROOT/'embedding'/payload['sources'][0]['filename']
    library = DocumentLibrary(database,store)
    documents = library.ingest([SourceFile.from_path(source)])
    assert [d.page_content for d in documents]==[c['text'] for c in payload['chunks']]
    assert max(len(d.page_content) for d in documents)<=500
    assert database.counts()==before_rows
    assert store.index.ntotal==before_vectors
    library.ingest([SourceFile.from_path(source)])
    assert database.counts()==before_rows
    assert store.load() and store.index.ntotal==before_vectors
    report = dict(database='MySQL',document_rows=database.counts(),
        original_pdf_chunks=len(documents),saved_index_vectors=store.index.ntotal,
        vector_dimension=store.index.d,maximum_chunk_characters=max(len(d.page_content) for d in documents),
        duplicate_upload=True,persisted_reload=True,external_api_requests=0,
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((ROOT/'lab9_core').glob('*.py'))})
    (ROOT/'results/library.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
