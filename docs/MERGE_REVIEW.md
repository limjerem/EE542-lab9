# Remote merge and progress review

This is the merge-time snapshot. Part 5 was implemented and verified afterward;
see PART5.md and results/part5 for the later experiment and current status.

The working repository is `/home/n0tsync/Documents/EE542/Lab9/EE542-lab9`.
Remote main was fast-forwarded from `48f5208` to `ed37871`. Jason's commits
`2d011e0` and `bae98a2`, the merge commit, and all earlier authors/history remain
intact. No local commit or push was made.

## Preserved work and conflict resolution

All 12 modified tracked files and 14 untracked files were copied and verified by
SHA-256 before synchronization. The private backup and original-base snapshots are
under `../local_backups/before-remote-merge-r4s3obkj`.

Five files needed reconciliation: backend app/requirements and the three frontend
files. The result retains the Part 4 shared upload/retrieval service, reply queue,
persisted citations and responsive interface while incorporating direct bcrypt,
trimmed username/72-byte password validation, asynchronous hashing, authenticated
WebSockets and connection-before-history synchronization. Both the previous
auth/connected exchange and the contributor's authenticate/ready exchange work.
The Part 1 verifier now understands queue events and the document assistant.

The contributor's Part 3 fixes remain in place: matching index/metadata snapshots,
explicit UTF-8 reads, historical source display, reuse-only settings and safe quota
messages. Five imported regressions were retained; Unicode fixtures use English
text with accented/math characters. Imported reports were translated to English
and distinguish reported outcomes from locally available evidence. README stays
brief. The project virtual environment uses bcrypt 4.3.0; the Conda installation
was not changed.

## Verification after merging

| Check | Actual result | Evidence |
|---|---|---|
| Offline regressions | 20 passed | `results/merge-review/tests.txt` |
| Live Part 1 services | 42 checks passed; own test data cleaned | `results/merge-review/part1-verification.json` |
| Part 3 SQL/index persistence | 5 documents, 128 pages, 784 chunks/vectors; duplicate/reload passed | `results/merge-review/library.json` |
| Part 3 browser uploads | Six scenarios passed, no questions submitted | `results/merge-review/upload-ui.json` |
| Part 4 real browser integration | 17 checks passed | `results/part4/verification.json` |
| Dependency consistency | pip check passed | `results/merge-review/pip-check.txt` |

The real browser run uses the shared upload backend, MySQL and the existing local
Llama model. It checks duplicate upload, a new cached-text upload entering the chat
index, retry without vector duplication, a visible uncached-upload failure, two
accounts, live messages, follow-up, citations after reload, reconnect, error input
preservation, literal HTML text, narrow layout, logout and invalid credentials.
The three questions cover ADS tuning, optimization and an unsupported cake recipe.
The first two received cited answers; the third was declined for lack of evidence.

Zero document embedding requests were made. One new question vector was needed
for a locally rewritten follow-up. Cloud answer generation was not used. The
original native index retains 771 vectors; the shared knowledge base retains five
documents and 784 vectors. Temporary upload probes were removed. Existing synthetic
validation accounts/messages remain as records; the Part 1 verifier cleaned only
its own accounts/messages. The original source indexes were not rebuilt.

Preliminary attempts are explicitly recorded in `results/merge-review/review.json`:
the temporary browser installation was missing, and a subsequent strict
query-cache-only run stopped at an uncached rewrite. The browser was restored and
the final run allowed that necessary question vector while retaining the document
embedding guard. No model was downloaded.

## Current progress

| Part | Assessment |
|---|---|
| 1: Web chat | Complete for the integrated website; reverified on WSL |
| 2: Android TWA | Contributor reports completion on Windows; source/configuration merged, APK/screenshots/detailed device logs not included |
| 3: Upload and OpenAI RAG | Core workflow complete; merged fixes and real SQL/upload checks passed; previous OpenAI answer acceptance retained without repeating it |
| 4: Domain chatbot website | Integrated and verified against the real shared upload backend |
| 4: Android and full curated corpus | New website's upload/retrieval/citation flow still needs Android acceptance; six-source import was not rerun on WSL |
| 5: Custom embedding | Word2Vec, custom K-means, normalized histograms and improvement experiments not implemented/verified in this repository |
| Video | Three short speaker scripts drafted in conversation; no recording produced |

`PART2.md` references 16 HTTPS checks and 9 TWA/login checks from the contributor's
machine. Its APK, final TWA screenshot and detailed JSON records are absent from
the remote Git tree; absence does not disprove the contributor's run, but prevents
independent inspection here. That earlier general-chat run also does not establish
Android acceptance of the newly integrated Part 4 document assistant.

Remaining work is to collect the contributor's device evidence, verify the merged
Part 4 flow in that Android environment, reconcile the intended curated corpus,
perform Part 5 experiments when authorized, and record the final demonstration.
Integration and review files were uncommitted at review time. The user later
authorized publishing them together with the completed Part 5 work. Snapshot
JSON fields describing that earlier Git state are retained as recorded.
