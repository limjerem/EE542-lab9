# Part 4 integration

## Shared upload and retrieval

The upload module exports `create_documents_router(current_user)` and
`init_documents_db()`. The application registers that router and initializes its
kb_documents/kb_chunks tables during startup. Authentication is passed as a
dependency, avoiding a circular import of app.py.

- GET /api/documents lists filename, pages, chunks, status and error.
- POST /api/documents accepts multipart `files` and returns `results`.
- POST /api/documents/{id}/retry retries stored chunks.
- DELETE /api/documents/{id} removes the selected document and vectors.
- Status is processing, indexed or failed. Upload result is indexed, duplicate,
  retried, processing, failed or rejected. The frontend handles those actual values,
  preserves selected files on failure, and shows Retry indexing for failed records.

`knowledge_adapter.shared_kb()` connects the upload store to a persistent embedding
cache. It reuses compatible vectors from the existing Part 3 cache and preserves
successful batches on later failures. `ChatKnowledgeIndex` reads the same shared
knowledge base, so added/deleted documents become visible without restarting chat.
Question vectors have a separate cache and never invoke document embedding methods.

KB_DIR selects the upload store (default kb_store). An empty value also selects the
default. RAG_QUERY_CACHE_DIR can override the existing Part 3 cache directory;
otherwise PART3_INDEX_DIR in embedding/.env.upload is used. Keep the embedding model
and provider consistent across upload and query. Current validation uses OpenAI
text-embedding-3-small and the existing 1536-dimensional vectors.

The web application loads its asyncmy database configuration first, then fills
missing OpenAI settings from embedding/.env. The Part 3 synchronous database DSN is
not passed to the web application's async engine.

## Existing data

`scripts/reuse_part3_knowledge.py` copies existing source text and exact FAISS vectors
into the upload tables/store without embedding them again. Run it while the web
process is stopped. Existing rag_* tables and FAISS snapshots remain intact. The
local run reused five documents and 784 vectors; `results/part4/sync-migration.json`
records the result. It does not claim that all six curated sources were re-ingested.

`data/SOURCES.md` preserves the source-selection record in English. Its corpus
counts describe the contributor's extraction, while local reused chunk counts are
recorded separately. Their different split configurations are not interchangeable.

## Chat API and events

GET /api/knowledge reports topic, ready, indexed_chunks, documents and
uploads_available. POST /api/messages immediately returns ok, message and
bot_pending. A question mark or @bot queues an assistant response; plain group
messages are broadcast without inference.

GET /api/messages returns messages and current pending_replies. Bot messages include
reply_to, status and ordered sources with label, filename, page, chunk_id and text.
The additive message_evidence table preserves this information after refresh.

WebSocket /ws requires an initial authenticate message with the JWT. A valid client
receives a ready event. The earlier auth/connected exchange remains supported for
existing clients. Invalid sessions close with code 4401. Message events carry a message; bot_status events carry
request_id and queued/thinking/error status. Clients deduplicate IDs and synchronize
history after reconnection.

The frontend waits for the authenticated socket before loading history, merging
broadcasts received during the history request. Passwords use direct bcrypt with
the contributor's username and 72-byte password validation.

All accounts share one room. Prior messages resolve follow-ups, while only current
retrieved passages support facts. The single worker preserves question order and
excludes later user messages from earlier questions. The queue is in memory: a
process shutdown can discard pending work, and the user must resend an unanswered
question after restart. Completed replies and evidence are stored in MySQL.

## Boundaries

This delivery covers web integration and its checks. Android and custom embedding
experiments are separate. Single-process writes are supported. The upload store
replaces its vector and metadata files separately; an interruption between those
replacements can require index recovery. Cached vectors and the preserved Part 3
snapshot remain available for that recovery.
