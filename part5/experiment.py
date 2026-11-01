"""Train real Word2Vec, select on development queries, then evaluate held-out queries."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import time

from gensim.models import Word2Vec
from gensim.models.callbacks import CallbackAny2Vec
from gensim.models.word2vec import FAST_VERSION
import numpy as np

from .histogram import HistogramIndex, METHODS, normalize_rows, sha256, tokenize
from .kmeans import kmeans, squared_distances

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


class TrainingLog(CallbackAny2Vec):
    def __init__(self):
        self.epochs = []
        self.previous = 0

    def on_epoch_end(self, model):
        loss = float(model.get_latest_training_loss())
        self.epochs.append(dict(epoch=len(self.epochs) + 1,
                                reported_cumulative_loss=loss, epoch_loss=loss - self.previous))
        self.previous = loss


def train_word2vec(sentences, seed, dimension, epochs, directory):
    directory.mkdir(parents=True, exist_ok=False)
    log = TrainingLog()
    started = time.perf_counter()
    model = Word2Vec(sentences=sentences, vector_size=dimension, window=5,
                     min_count=1, sg=1, negative=10, sample=1e-3, workers=1,
                     seed=seed, epochs=epochs, compute_loss=True, callbacks=[log])
    model.save(str(directory / 'word2vec.model'))
    np.save(directory / 'raw_word_vectors.npy', model.wv.vectors)
    training = dict(seed=seed, algorithm='Gensim skip-gram with negative sampling',
                    gensim_version=importlib.metadata.version('gensim'), fast_version=FAST_VERSION,
                    fallback_used=False, pretrained_vectors=False, vector_size=dimension,
                    window=5, min_count=1, sg=1, negative=10, sample=1e-3, workers=1,
                    epochs=epochs, pythonhashseed=os.getenv('PYTHONHASHSEED'),
                    vocabulary_size=len(model.wv), corpus_count=model.corpus_count,
                    corpus_total_words=model.corpus_total_words,
                    seconds=time.perf_counter() - started, training_loss=log.epochs,
                    model_sha256=sha256(directory / 'word2vec.model'),
                    raw_vectors_sha256=sha256(directory / 'raw_word_vectors.npy'))
    return model, training


def evaluate(index, queries, method, alpha=0.5):
    details = []
    for query in queries:
        matches, coverage = index.search(query['question'], method, alpha, k=10)
        pages = [match['document']['page'] for match in matches]
        first = next((rank for rank, page in enumerate(pages, 1)
                      if page in query['relevant_pages']), None)
        details.append(dict(id=query['id'], question=query['question'],
                            relevant_pages=query['relevant_pages'], retrieved_pages=pages,
                            chunk_ids=[m['document']['chunk_id'] for m in matches],
                            first_relevant_rank=first, coverage=coverage,
                            reciprocal_rank=1 / first if first else 0,
                            **{f'hit_at_{k}': int(first is not None and first <= k) for k in [1, 3, 5]}))
    metrics = {name: float(np.mean([row[name] for row in details]))
               for name in ['hit_at_1', 'hit_at_3', 'hit_at_5', 'reciprocal_rank']}
    metrics['mrr_at_10'] = metrics.pop('reciprocal_rank')
    metrics['queries'] = len(details)
    return metrics, details


def selection_key(metrics):
    return metrics['mrr_at_10'], metrics['hit_at_5'], metrics['hit_at_1']


def fit_index(model, documents, k, seed, corpus_hash, destination):
    words = list(model.wv.index_to_key)
    vectors = normalize_rows(model.wv.vectors.astype(np.float64))
    started = time.perf_counter()
    result = kmeans(vectors, k, seed=seed, n_init=3, max_iter=200)
    if not result.converged:
        raise RuntimeError('K-means did not reach a fixed point; do not publish incomplete centroids')
    nearest = squared_distances(vectors, result.centers).argmin(axis=1)
    assert np.array_equal(nearest, result.labels)
    means = np.vstack([vectors[result.labels == label].mean(axis=0) for label in range(k)])
    assert np.allclose(result.centers, means, atol=1e-10)
    index = HistogramIndex(words, vectors, result.centers, documents,
                           metadata=dict(seed=seed, k=k, corpus_sha256=corpus_hash,
                                         word_vectors='L2-normalized trained Word2Vec vectors'))
    histogram = index.matrices['hard_histogram']
    assert histogram.shape == (len(documents), k)
    assert np.isfinite(histogram).all() and (histogram >= 0).all()
    assert np.allclose(histogram.sum(axis=1), 1)
    assert np.all(index.counts.sum(axis=1) == index.totals)
    index.save(destination)
    reloaded = HistogramIndex.load(destination)
    assert np.array_equal(reloaded.matrices['hard_histogram'], histogram)
    trace = dict(seed=seed, k=k, restarts=3, selected_restart=result.restart,
                 inertia=result.inertia, iterations=len(result.history), converged=result.converged,
                 empty_cluster_repairs=result.empty_repairs, cluster_sizes=np.bincount(result.labels).tolist(),
                 history=result.history, seconds=time.perf_counter() - started,
                 labels_match_nearest_centers=True, centers_match_assigned_means=True,
                 maximum_histogram_sum_error=float(abs(histogram.sum(axis=1) - 1).max()),
                 dimension=list(histogram.shape), all_corpus_tokens_in_vocabulary=True,
                 artifact=str(destination.relative_to(ROOT)))
    np.save(destination / 'histograms.npy', histogram)
    np.save(destination / 'word_cluster_labels.npy', result.labels)
    return index, trace


def plots(output, metrics, traces, training, selected):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    methods = list(METHODS)
    labels = ['Hard histogram', 'Stopwords removed', 'TF-IDF + sqrt', 'Hybrid', 'Lexical TF-IDF']
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for axis, metric, title in zip(axes, ['hit_at_5', 'mrr_at_10'], ['Test Hit@5', 'Test MRR@10']):
        values = [next(row[metric] for row in metrics if row['seed'] == selected['seed']
                       and row['k'] == selected['k'] and row['split'] == 'test'
                       and row['method'] == method) for method in methods]
        axis.bar(range(len(values)), values, color=['#64748b', '#94a3b8', '#0891b2', '#2563eb', '#a78bfa'])
        axis.set(ylim=(0, 1), title=title, ylabel='Score')
        axis.set_xticks(range(len(labels)), labels, rotation=30, ha='right', fontsize=9)
        for i, value in enumerate(values):axis.text(i, value + .02, f'{value:.3f}', ha='center', fontsize=8)
    fig.suptitle('ADS cookbook: 18 held-out authored questions (page-level labels)')
    fig.savefig(output / 'retrieval-comparison.png', dpi=180)
    fig.savefig(output / 'retrieval-comparison.pdf')
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for trace in traces:
        if trace['seed'] == selected['seed']:
            axes[0].plot([p['iteration'] for p in trace['history']],
                         [p['inertia'] for p in trace['history']], label=f"K={trace['k']}")
    axes[0].set(title='Custom Lloyd convergence', xlabel='Iteration', ylabel='Within-cluster squared error')
    axes[0].legend()
    main_training = next(t for t in training if t['seed'] == selected['seed'])
    axes[1].plot([r['epoch'] for r in main_training['training_loss']],
                 [r['epoch_loss'] for r in main_training['training_loss']])
    axes[1].set(title='Word2Vec reported training loss', xlabel='Epoch', ylabel='Loss increment (not validation loss)')
    fig.savefig(output / 'training-and-clustering.png', dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'embedding/index_data/chunks.json')
    parser.add_argument('--evaluation', type=Path, default=ROOT / 'part5/evaluation.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/part5')
    parser.add_argument('--artifacts', type=Path, default=ROOT / 'local_artifacts/part5')
    parser.add_argument('--dimension', type=int, default=100)
    parser.add_argument('--epochs', type=int, default=30)
    args = parser.parse_args()
    args.corpus = args.corpus.resolve()
    args.evaluation = args.evaluation.resolve()
    if os.getenv('PYTHONHASHSEED') != '0':
        parser.error('Run with PYTHONHASHSEED=0 for reproducible Word2Vec initialization')
    if args.dimension < 1 or args.epochs < 1:
        parser.error('Dimension and epochs must be positive')
    output = args.output.resolve()
    if (output / 'summary.json').exists():
        parser.error('Results already exist; select a new --output to preserve the previous experiment')
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    artifacts = args.artifacts.resolve() / ('run-' + stamp)
    artifacts.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=True)
    payload = json.loads(args.corpus.read_text(encoding='utf-8'))
    documents = payload['chunks']
    if len({c['chunk_id'] for c in documents}) != len(documents):
        raise ValueError('Duplicate corpus chunk identifiers')
    sentences = [tokenize(document['text']) for document in documents]
    if not all(sentences):
        raise ValueError('Empty tokenized chunk; define a deliberate corpus policy before training')
    dataset = json.loads(args.evaluation.read_text(encoding='utf-8'))
    for query in dataset['queries']:
        for page in query['relevant_pages']:
            if not any(d['page'] == page and query['evidence_anchor'].lower()
                       in ' '.join(d['text'].split()).lower() for d in documents):
                raise ValueError('Missing labeled evidence: ' + query['id'])
    dev = [q for q in dataset['queries'] if q['split'] == 'dev']
    test = [q for q in dataset['queries'] if q['split'] == 'test']
    if not dev or not test or len({q['id'] for q in dataset['queries']}) != len(dataset['queries']):
        raise ValueError('Invalid development/test split')
    corpus_hash = sha256(args.corpus)
    write_json(output / 'protocol.json', dict(corpus_sha256=corpus_hash,
        evaluation_sha256=sha256(args.evaluation), development_ids=[q['id'] for q in dev],
        test_ids=[q['id'] for q in test], k_candidates=[32, 64, 128], hybrid_alphas=[.25, .5, .75],
        primary_seed=542, additional_seeds=[42, 2026], dimension=args.dimension, epochs=args.epochs,
        selection='Maximize development MRR@10, then Hit@5, then Hit@1; ties choose smaller K/alpha.',
        training='Only corpus tokens; no question text or relevance labels enter Word2Vec, clustering or IDF.'))
    models, indexes, traces, training, metrics, query_results = {}, {}, [], [], [], []
    model, train_record = train_word2vec(sentences, 542, args.dimension, args.epochs, artifacts / 'seed542')
    models[542] = model
    training.append(train_record)
    for k in [32, 64, 128]:
        print(f'Trained Word2Vec; fitting custom K-means K={k}', flush=True)
        index, trace = fit_index(model, documents, k, 542, corpus_hash, artifacts / f'seed542/k{k}')
        indexes[k] = index
        traces.append(trace)
        for method in METHODS:
            for alpha in ([.25, .5, .75] if method == 'hybrid_tfidf' else [.5]):
                score, _ = evaluate(index, dev, method, alpha)
                metrics.append(dict(seed=542, k=k, method=method, alpha=alpha, split='dev', **score))
    # Freeze choices before the first held-out evaluation.
    chosen = max((row for row in metrics if row['method'] == 'tfidf_hellinger'),
                 key=lambda r: (*selection_key(r), -r['k']))
    k = chosen['k']
    alpha = max((row for row in metrics if row['k'] == k and row['method'] == 'hybrid_tfidf'),
                key=lambda r: (*selection_key(r), -r['alpha']))['alpha']
    selected = dict(seed=542, k=k, hybrid_alpha=alpha,
                    artifact_directory=str((artifacts / f'seed542/k{k}').relative_to(ROOT)),
                    selection_split='dev', primary_histogram='tfidf_hellinger')
    write_json(output / 'selection.json', selected)
    for seed in [542, 42, 2026]:
        if seed != 542:
            model, record = train_word2vec(sentences, seed, args.dimension, args.epochs, artifacts / f'seed{seed}')
            models[seed] = model
            training.append(record)
            index, trace = fit_index(model, documents, k, seed, corpus_hash, artifacts / f'seed{seed}/k{k}')
            traces.append(trace)
        else:
            index = indexes[k]
        for method in METHODS:
            for split, queries in [('dev', dev), ('test', test)]:
                score, details = evaluate(index, queries, method, alpha)
                row = dict(seed=seed, k=k, method=method, alpha=alpha if method == 'hybrid_tfidf' else .5,
                           split=split, **score)
                # Replace the selected development configuration rather than duplicating it.
                metrics = [r for r in metrics if not all(r[key] == row[key]
                           for key in ['seed', 'k', 'method', 'alpha', 'split'])]
                metrics.append(row)
                query_results.append(dict(seed=seed, k=k, method=method, split=split, queries=details))
        print(f'Seed {seed} evaluated at frozen K={k}, alpha={alpha}', flush=True)
    main_index = indexes[k]
    controls = []
    for query in dataset['controls']:
        for method in METHODS:
            matches, coverage = main_index.search(query['question'], method, alpha)
            assert not matches, 'Unexpected retrieval for unknown/all-stopword control'
            controls.append(dict(id=query['id'], method=method, abstained=True, coverage=coverage))
    word = 'tuning'
    word_id = main_index.word_index[word]
    example_document = next(d for d in documents if d['page'] == 5 and 'What is Tuning?' in d['text'])
    document_id = documents.index(example_document)
    query_vector, coverage = main_index.query_features(dev[0]['question'])
    example = dict(word=word, word_vector=models[542].wv[word].astype(float).tolist(),
        normalized_word_vector=main_index.vectors[word_id].tolist(),
        assigned_bin=int(main_index.codes[word_id]),
        centroid=main_index.centers[main_index.codes[word_id]].tolist(),
        document=example_document, document_tokens=int(main_index.totals[document_id]),
        document_histogram=main_index.matrices['hard_histogram'][document_id].tolist(),
        document_histogram_sum=float(main_index.matrices['hard_histogram'][document_id].sum()),
        query=dev[0]['question'], query_histogram=query_vector.tolist(), query_coverage=coverage,
        explanation='Each token is assigned to its nearest centroid. The baseline divides bin counts by all tokenized words in the chunk. Unknown query tokens contribute no bin mass; their fraction is reported.')
    write_json(output / 'embedding-example.json', example)
    groups = []
    for label in range(k):
        members = np.flatnonzero(main_index.codes == label)
        distances = np.square(main_index.vectors[members] - main_index.centers[label]).sum(axis=1)
        closest = members[np.argsort(distances)[:12]]
        groups.append(dict(bin=label, word_types=len(members), representative_words=[main_index.vocabulary[i] for i in closest]))
    write_json(output / 'word-groups.json', groups)
    write_json(output / 'training.json', training)
    write_json(output / 'clustering.json', traces)
    write_json(output / 'per-query.json', query_results)
    write_json(output / 'controls.json', controls)
    with (output / 'metrics.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    summary = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_changes_uncommitted=True, configured_git_author=subprocess.check_output(
            ['git', 'var', 'GIT_AUTHOR_IDENT'], cwd=ROOT, text=True).split('>')[0] + '>',
        corpus=dict(source=args.corpus.relative_to(ROOT).as_posix(), sha256=corpus_hash,
                    documents=payload['sources'], chunks=len(documents),
                    token_occurrences=sum(map(len, sentences)), vocabulary_size=len(main_index.vocabulary),
                    overlap_retained=payload['chunk_overlap']),
        selected=selected, held_out_questions=len(test), development_questions=len(dev),
        primary_seed_test=[r for r in metrics if r['seed'] == 542 and r['k'] == k and r['split'] == 'test'],
        seed_robustness={method: {metric: dict(mean=float(np.mean(values)), std=float(np.std(values)))
            for metric in ['hit_at_5', 'mrr_at_10']
            for values in [[r[metric] for r in metrics if r['k'] == k and r['split'] == 'test' and r['method'] == method]]}
            for method in METHODS},
        seconds=time.perf_counter() - started, paid_api_requests=0,
        packages={name: importlib.metadata.version(name) for name in ['gensim', 'numpy', 'scipy', 'matplotlib']},
        python=platform.python_version(), platform=platform.platform(),
        code_sha256={p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / 'part5').glob('*.py'))},
        limitations=['One small English course document; vocabulary includes rare extraction artifacts.',
                    'Questions and page labels are Codex-assisted authored diagnostics, not independently adjudicated.',
                    'Page relevance is coarse and not exhaustive; overlap creates related chunks.',
                    'Development/test queries are held out from fitting, not the source document itself.',
                    'Hybrid adds lexical TF-IDF scores; it is not a pure K-dimensional histogram improvement.'])
    plots(output, metrics, traces, training, selected)
    write_json(output / 'summary.json', summary)
    write_json(artifacts / 'latest.json', selected)
    print(json.dumps(dict(selected=selected, test=summary['primary_seed_test'],
                          seconds=summary['seconds'], paid_api_requests=0), indent=2), flush=True)


if __name__ == '__main__':
    main()
