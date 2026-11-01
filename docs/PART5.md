# Part 5: Word2Vec and custom word-group histograms

This implementation covers the assignment's local custom-embedding experiment.
It does not replace the shared Part 4 service. Source, tests and public results are
in `part5/`, `tests/test_part5.py` and `results/part5/`. All commands below run from
`/home/n0tsync/Documents/EE542/Lab9/EE542-lab9`.

## Data and actual training

The frozen input is `embedding/index_data/chunks.json`: 771 existing chunks from
the 124-page course-provided ADS Circuit Design Cookbook. Its SHA-256 is recorded
in `results/part5/protocol.json`. The original 500-character splitting and
100-character overlap are retained. Repeated text from overlapping chunks is not
deduplicated during training. The separate upload-test excerpts are excluded.
Neither the source PDF nor the original OpenAI indexes are rebuilt.

Tokenization lowercases NFKC text, joins alphabetic words split by a hyphen/newline,
retains alphanumeric RF terms such as S11, and drops standalone numbers. The
result has 53,001 token occurrences and 4,054 distinct tokens. Rare PDF extraction
artifacts remain; this is a small domain corpus, not a general language model.

Real [Gensim Word2Vec](https://radimrehurek.com/gensim/models/word2vec.html) trains
skip-gram with negative sampling: N=100, window=5, negative=10, min_count=1,
sample=0.001, 30 epochs, one worker. min_count=1 retains every token used in the
document histograms. Runs use seeds 542, 42 and 2026, PYTHONHASHSEED=0 and a single
BLAS thread. See [Mikolov et al.](https://arxiv.org/abs/1301.3781) for the original
word-vector method. Training does not use pretrained vectors or a fallback.
`training.json` contains real loss snapshots and model/vector hashes. The loss is
the trainer's reported training objective, not validation loss or answer accuracy.

## Custom clustering and required embedding

The trained N-dimensional word vectors are L2-normalized before Euclidean
clustering. Each distinct vocabulary word contributes one point. Our
`part5/kmeans.py` implements [k-means++ seeding](https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf)
and Lloyd updates with three restarts. It uses no library clustering routine.
An empty cluster takes the farthest point from a non-singleton cluster. Convergence
requires nearest-center assignments to agree with the updated centroid means;
nonconverged outputs are rejected by the experiment. Saved traces expose SSE,
iterations, cluster sizes and the selected restart.

For vocabulary word w, assign b(w) to its nearest centroid. For a chunk with L
tokenized words, the required baseline is:

```text
h[j] = count(tokens w with b(w) = j) / L, for j = 0, ..., K-1
```

K is both the cluster count and the baseline embedding dimension. On this corpus,
every token is in vocabulary, so every baseline vector is nonnegative and sums to
one. Development selection chose K=128, producing a 771 x 128 matrix. Queries use
the same vocabulary, centroids and bin assignment. Unknown query tokens contribute
no mass but remain in L; the sum then equals the known-token fraction. Coverage
is reported, and zero-content queries return no matches. There is no default-bin
assignment for unknown words.

Cosine similarity ranks chunks. Histogram/vector/label artifacts can be saved and
reloaded; checksums are verified and NumPy loading disables pickle. The full Gensim
training model is retained locally for provenance; retrieval does not load it.

## Improvements and controlled evaluation

The compared representations are:

1. Hard histogram: the assignment's K-bin count/L vector.
2. Stopword histogram: remove Gensim English stopwords and renormalize counts.
3. TF-IDF + square root: remove stopwords, use sublinear term frequency and
   corpus-only word IDF, accumulate weights by bin, divide by their sum, then take
   the square root. This remains K-dimensional; the square-root vector has unit L2
   norm rather than unit L1 sum.
4. Hybrid: alpha times weighted-histogram cosine plus (1-alpha) times lexical
   TF-IDF cosine. This combines two retrieval signals and is not a pure K-dimensional
   representation.
5. Lexical TF-IDF: a reference without word-group histograms.

`part5/evaluation.json` was frozen before training: 12 development questions, 18
held-out test questions, and three unsupported/empty-content controls. Questions
and relevance labels were authored with Codex assistance and checked against
source-page anchors. These are small course-specific diagnostics. Labels are
page-level, coarse and potentially incomplete, not independently adjudicated.
Related questions can concern the same chapter in both splits. All corpus pages
are visible to unsupervised fitting; test question text and labels are not.

K candidates are 32, 64 and 128. The primary weighted histogram selects K using
development MRR@10, then Hit@5, then Hit@1; a tie prefers smaller K. Hybrid alpha
is selected from 0.25, 0.5 and 0.75 on development questions only. Choices were
written to `selection.json` before evaluating test questions. The additional two
training seeds reuse K=128 and alpha=0.25 without retuning.

Hit@k is the fraction of questions with a labeled page among the first k retrieved
chunks. MRR@10 averages the reciprocal rank of the first labeled page within ten
chunks, using zero for a miss. It is not answer accuracy or confidence.

## Measured results

Primary seed 542, K=128, 18 held-out questions:

| Method | Hit@1 | Hit@5 | MRR@10 |
|---|---:|---:|---:|
| Required hard histogram | 27.8% | 50.0% | 0.373 |
| Stopword histogram | 38.9% | 55.6% | 0.449 |
| TF-IDF + square root | 38.9% | 61.1% | 0.481 |
| Hybrid, alpha=0.25 | 83.3% | 100.0% | 0.881 |
| Lexical TF-IDF reference | 88.9% | 100.0% | 0.919 |

Across three training seeds, hard-histogram Hit@5 is 61.1% +/- 7.9 percentage
points, weighted-histogram Hit@5 is 64.8% +/- 5.2 points, and hybrid Hit@5 is
96.3% +/- 2.6 points (population standard deviation). Mean MRR@10 is 0.418,
0.487 and 0.861 respectively. Lexical TF-IDF remains at Hit@5=100% and MRR@10=0.919.

The weighted histogram improves the primary run and average MRR, but the pure
lexical reference ranks this small diagnostic better than the hybrid. There is no
claim that word grouping beats lexical retrieval or that these percentages
generalize to unseen users or other documents. Complete per-question failures,
all three seeds and development candidates remain in CSV/JSON.

The primary K-means runs converged in 45, 46 and 20 iterations for K=32, 64 and 128.
The 128-bin document vectors, word labels and centroids were checked for agreement.
Retraining seed 542 reproduced every word-vector component exactly on this
environment. No OpenAI or other paid API was used.

## Real retrieval and local RAG

`part5/cli.py` independently loads the custom index and can pass its retrieved
chunks to the existing loopback Llama endpoint. The actual verification used the
pure weighted histogram, six passages, and no OpenAI embeddings:

- Tuning: the local model explained changing component values and observing circuit
  performance, citing retrieved source [5].
- Branch-line coupler: it answered a 90-degree output phase difference with sources
  [1, 2].
- Cake recipe: no content words were in the vocabulary, so the application declined
  before calling the model.

This unknown-token check is not a general out-of-domain detector. An unrelated
question sharing vocabulary can still retrieve passages; the grounding prompt
does not provide a formal factuality guarantee. Low-rank relevant passages also
remain a real limitation of the pure histogram.

`results/part5/verification.json` records eight passed verification groups,
including real same-seed retraining, persisted metric recomputation and those
local RAG outcomes. All 30 repository regression tests passed, including ten new
Part 5 cases; the output is in `results/part5/tests.txt`. Dependency consistency
also passed `pip check`. `embedding-example.json` contains an actual 100-dimensional
word vector, its assigned centroid, a real source chunk, its 128-dimensional
baseline histogram and the question histogram. `word-groups.json` lists actual
representative words for each bin. PNG/PDF plots are ready for the video.

## Run and reproduce

Install only into the project virtual environment if needed:

```bash
.venv/bin/python -m pip install -r part5/requirements.txt
```

The existing selected artifact is under the path recorded in
`results/part5/selection.json`. It is ignored by Git and must be retained locally
or regenerated after cloning. Corpus chunks are also private local artifacts.

Inspect the required baseline or use the improved custom retrieval with Llama:

```bash
.venv/bin/python -m part5.cli --question "What is tuning used for in ADS?" --method hard_histogram --k 3
.venv/bin/python -m part5.cli --question "What is tuning used for in ADS?" --method tfidf_hellinger --k 6 --answer
.venv/bin/python -m part5.cli --method hybrid_tfidf --answer
```

The last command enters a loop; type `exit` to quit. Use self-contained questions;
this Part 5 demonstration does not implement conversation reference rewriting.
The local-answer option accepts only a loopback model endpoint. It uses the existing
`groupchat_app_src/.env` model configuration and does not alter the shared website.

Reproduce the experiment without overwriting the recorded results:

```bash
PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/ee542-lab9-matplotlib .venv/bin/python -m part5.experiment \
  --output local_artifacts/part5/reproduction-results
```

Recheck the saved primary model, retrain one seed and run the three local examples:

```bash
PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m part5.verify --live-rag
```

Omit `--live-rag` for the entirely offline verification. Repeated verification
overwrites only verification.json, not training results or the source indexes.
The Part 4 website, uploads, Android integration and original RAG services remain
separate responsibilities. The user authorized publishing these source/results
together with the earlier local integration changes. Run metadata retains the
base commit and uncommitted state at measurement time, before that publication.
