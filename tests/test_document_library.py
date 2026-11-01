from pathlib import Path
import sys

from sqlalchemy import text

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab9_core.database import Database
from lab9_core.library import SourceFile, DocumentLibrary
from lab9_core.vector_store import VectorStore


class Embeddings:
    calls = 0
    def embed_documents(self, texts):
        self.calls += len(texts)
        return [[1.,float(len(t)),3.] for t in texts]
    def embed_query(self, text):
        return [1.,2.,3.]


def test_multiple_sources_and_repeat_content_use_one_cached_vector(tmp_path):
    embedding = Embeddings()
    database = Database('sqlite:///'+str(tmp_path/'documents.db'))
    vectors = VectorStore(tmp_path/'index',embedding,{'backend':'test'})
    library = DocumentLibrary(database,vectors)
    content = b'ADS tuning changes component values.'
    documents = library.ingest([SourceFile('ADS.txt',content),
        SourceFile('ADS.html',b'<html><body>'+content+b'</body></html>')])
    assert len(documents)==2 and embedding.calls==1
    first = database.counts()
    library.ingest([SourceFile('ADS.txt',content),SourceFile('same.txt',content)])
    assert database.counts()==first
    assert vectors.index.ntotal==2 and embedding.calls==1
    assert vectors.load()
    assert vectors.index.ntotal==2


def test_long_text_is_bounded_and_saved_in_order(tmp_path):
    database = Database('sqlite:///'+str(tmp_path/'documents.db'))
    vectors = VectorStore(tmp_path/'index',Embeddings(),{'backend':'test'})
    library = DocumentLibrary(database,vectors)
    documents = library.ingest([SourceFile('long.txt',b'tuning '*250)])
    assert max(len(d.page_content) for d in documents)<=500
    assert database.counts()['rag_chunks']==len(documents)
    with database.engine.connect() as connection:
        assert connection.scalar(text('SELECT COUNT(DISTINCT chunk_index) FROM rag_chunks'))==len(documents)
