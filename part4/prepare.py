"""Build the formal, deduplicated ADS collection using the Part 3 vector layer."""
from pathlib import Path
import hashlib, json, sys
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from lab9_core.library import SourceFile, settings
from lab9_core.vector_store import VectorStore
from part4.storage import StudyStore
from part4.collect import collect

DIRECTORY = ROOT/'local_artifacts/part4'

def build():
    manifest = json.loads((ROOT/'part4/corpus.json').read_text(encoding='utf-8'))
    collect(manifest,DIRECTORY/'corpus')
    (ROOT/'outputs/part4').mkdir(parents=True,exist_ok=True)
    values = settings();model = values.get('EMBEDDING_MODEL','text-embedding-3-small')
    real = OpenAIEmbeddings(model=model,api_key=values.get('OPENAI_API_KEY'),request_timeout=60)
    class Progress:
        count = 0
        def embed_documents(self,texts):
            result = real.embed_documents(texts);self.count += len(texts)
            print('EMBEDDED_NEW_CHUNKS',self.count,flush=True);return result
        def embed_query(self,text):return real.embed_query(text)
    embedding = Progress()
    vectors = VectorStore(DIRECTORY/'index',embedding,dict(backend='openai',model=model,api_base='https://api.openai.com/v1'))
    vectors.seed_cache(ROOT/'embedding/index_data')
    splitter = CharacterTextSplitter(separator='\n',chunk_size=500,chunk_overlap=100)
    bounded = CharacterTextSplitter(separator='',chunk_size=500,chunk_overlap=100)
    selected, seen, extracted = [], set(), {}
    for source in manifest['sources']:
        path = DIRECTORY/'corpus'/source['filename']
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:raise ValueError('Document checksum mismatch')
        texts = SourceFile.from_path(path).page_text();extracted[source['id']] = texts
        count = 0
        for page,text in enumerate(texts,1):
            if page <= source['skip_pages']:continue
            for section in splitter.split_text(text):
                for piece in bounded.split_text(section) if len(section)>500 else [section]:
                    digest = hashlib.sha256(piece.encode()).hexdigest()
                    if len(piece.strip())<40 or digest in seen:continue
                    seen.add(digest)
                    selected.append(Document(page_content=piece,metadata=dict(source=source['filename'],source_id=source['id'],
                        page=page,chunk_id=f"{source['id']}:{digest}",title=source['title'],edition=source['edition'],
                        url=source['url'],publisher=source['publisher'])))
                    count += 1
        print('CURATED_CHUNKS',source['id'],count,flush=True)
    vectors.replace_documents(selected)
    StudyStore(values['DATABASE_URL']).publish_corpus(manifest,extracted,selected)
    report = dict(prepared_at=datetime.now(timezone.utc).isoformat(),source_count=len(manifest['sources']),
        pages=sum(s['pages'] for s in manifest['sources']),chunks=len(selected),dimension=vectors.index.d,
        generation=vectors.generation,new_embeddings=embedding.count,maximum_chunk_characters=max(len(d.page_content) for d in selected),
        excluded_test_excerpts=True,front_matter_excluded=True,deduplicated=True,embedding_model=model,
        per_source={s['id']:sum(d.metadata['source_id']==s['id'] for d in selected) for s in manifest['sources']})
    (DIRECTORY/'corpus-state.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (ROOT/'outputs/part4/corpus-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the project virtual environment')
    build()
