# Part 4 validation

The remote main branch was first synchronized to 48f5208, then fast-forwarded to
ed37871 without altering contributor authors or history. Existing B/C working
changes were backed up outside the repository and restored through a three-way
comparison. Authentication, dependencies and frontend conflicts were resolved by
combining the contributor's fixes with the Part 4 features. Integration changes
were uncommitted during validation and are included in the later user-authorized
publication. See MERGE_REVIEW.md for the merge-time progress assessment.

## Local checks

The regression suite uses temporary SQLite databases, fake embeddings, and mocked
Llama responses. It covers shared-room history ordering, authenticated WebSockets,
persisted citations, query-cache retry, missing indexes and the real upload router's
failed-then-successful indexing, duplicates and rejection. No paid API is used.

## Live integration

The browser script uses two real test accounts, local MySQL, the shared upload
knowledge base and the already installed local Llama. Document embedding is blocked
by RAG_REUSE_ONLY=1. The three ADS/general questions use cached query vectors when
available; document passages and history are sent only to the local answer model.

The live upload sequence checks a known duplicate, adds a temporary HTML file whose
text already has a cached vector, confirms the chat index increases, retries without
duplicating vectors, and exercises an uncached text file's explicit failure/retry
state. Only those two temporary verification documents are deleted afterward.

The report and screenshots in results/part4 describe the actual outcome. No result
from an upload mock is represented as backend acceptance. The six-source curated
corpus has not been rebuilt merely to repeat existing embedding work.

```bash
.venv/bin/python -m pytest tests -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/ee542-lab9-browsers \
  .venv/bin/python scripts/verify_part4.py
```

The browser script requires both local services, configured credentials, existing
vectors, the private excerpt fixtures and a reuse-only web process. Its run creates
named test accounts and chat messages as verification records. User passwords and
tokens are never included in the published report; temporary demo credentials are
kept in the ignored local_artifacts directory.

## Recorded outcome

- 20 regression tests passed after merging the contributor's five Part 3 regressions
  and adding a merged-authentication regression. The current output is in
  results/merge-review/tests.txt; results/part4/tests.txt contains the same latest run.
- 17 browser/integration checks passed against the actual upload backend.
- The local Llama answered the tuning question and optimization follow-up with
  numbered references, and declined the cake-recipe question for insufficient context.
- The migration reused 784 existing 1536-dimensional vectors with zero embedding requests.
- The final browser run added 1 query vector(s) to the cache.
  No document embedding or cloud answer request was made.
- The two temporary upload probes were removed after their checks; the five original
  documents and 784 vectors remain available.

The earlier B/C-only upload mocks were replaced by checks against the real router
and shared store in this final run. The report distinguishes an uncached upload
blocked by reuse-only mode from transient-provider recovery covered by regression tests.

The first merge-review browser attempt stopped before launch because its temporary
browser installation had been removed. After restoring the headless browser, a
strict query-cache-only attempt passed the first real answer but stopped at a new
follow-up rewrite. RAG_QUERY_REUSE_ONLY rejected that uncached query as intended.
The final complete run retained the document guard and generated one necessary
question vector. These preliminary failures are recorded in
results/merge-review/review.json rather than represented as successful runs.
