"""Recompute saved metrics, retrain one seed, and optionally exercise local RAG."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np

from .cli import local_answer
from .experiment import evaluate, train_word2vec, write_json
from .histogram import HistogramIndex, METHODS, sha256, tokenize

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT / 'results/part5')
    parser.add_argument('--live-rag', action='store_true')
    args = parser.parse_args()
    if os.getenv('PYTHONHASHSEED') != '0':parser.error('Run with PYTHONHASHSEED=0')
    summary = json.loads((args.results / 'summary.json').read_text(encoding='utf-8'))
    protocol = json.loads((args.results / 'protocol.json').read_text(encoding='utf-8'))
    selected = summary['selected']
    directory = ROOT / selected['artifact_directory']
    index = HistogramIndex.load(directory)
    corpus = ROOT / summary['corpus']['source']
    assert sha256(corpus) == protocol['corpus_sha256']
    assert sha256(ROOT / 'part5/evaluation.json') == protocol['evaluation_sha256']
    checks = ['corpus_and_evaluation_hashes', 'artifact_checksums_and_reload']
    baseline = index.matrices['hard_histogram']
    assert baseline.shape == (summary['corpus']['chunks'], selected['k'])
    assert np.isfinite(baseline).all() and (baseline >= 0).all()
    np.testing.assert_allclose(baseline.sum(axis=1), 1, atol=1e-12)
    np.testing.assert_array_equal(np.load(directory / 'histograms.npy', allow_pickle=False), baseline)
    checks.append('required_histogram_dimension_nonnegativity_and_normalization')
    labels = np.load(directory / 'word_cluster_labels.npy', allow_pickle=False)
    np.testing.assert_array_equal(index.codes, labels)
    for label in range(selected['k']):
        np.testing.assert_allclose(index.centers[label], index.vectors[labels == label].mean(axis=0), atol=1e-10)
    checks.append('nearest_centroid_labels_and_centroid_means_agree')
    dataset = json.loads((ROOT / 'part5/evaluation.json').read_text(encoding='utf-8'))
    test = [q for q in dataset['queries'] if q['split'] == 'test']
    for row in summary['primary_seed_test']:
        score, _ = evaluate(index, test, row['method'], row['alpha'])
        for name in ['hit_at_1', 'hit_at_3', 'hit_at_5', 'mrr_at_10']:
            assert abs(score[name] - row[name]) < 1e-12
    checks.append('held_out_metrics_recomputed_from_saved_model')
    for query in dataset['controls']:
        for method in METHODS:
            assert not index.search(query['question'], method, selected['hybrid_alpha'])[0]
    checks.append('unknown_and_stopword_controls_abstain')
    training = json.loads((args.results / 'training.json').read_text(encoding='utf-8'))
    primary = next(t for t in training if t['seed'] == selected['seed'])
    source = json.loads(corpus.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(dir=ROOT / 'local_artifacts/part5', prefix='retrain-check-') as temp:
        model, _ = train_word2vec([tokenize(c['text']) for c in source['chunks']], primary['seed'],
                                 primary['vector_size'], primary['epochs'], Path(temp) / 'model')
        original = np.load(directory.parent / 'raw_word_vectors.npy', allow_pickle=False)
        np.testing.assert_array_equal(model.wv.vectors, original)
    checks.append('actual_word2vec_retraining_reproduces_all_vectors_exactly')
    result = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), checks=checks,
                  status='passed', paid_api_requests=0, live_rag_requested=args.live_rag)
    if args.live_rag:
        answers = []
        for question in ['What is tuning used for in ADS?',
                         'What output phase difference does a branch line coupler produce?',
                         'How do I bake a chocolate cake?']:
            answer = local_answer(index, question, 'tfidf_hellinger', selected['hybrid_alpha'], k=6)
            print(question + '\n' + answer['answer'], flush=True)
            answers.append(answer)
        assert answers[0]['model_called'] and re.search(r'\[\d+\]', answers[0]['answer'])
        assert answers[1]['model_called'] and '90' in answers[1]['answer']
        assert not answers[2]['model_called'] and not answers[2]['sources']
        # Source text remains available in local artifacts; publish compact references.
        for answer in answers:
            for source in answer['sources']:source.pop('text', None)
        result['answers'] = answers
        checks.append('real_local_llama_answers_from_custom_histogram_retrieval')
    write_json(args.results / 'verification.json', result)
    print(json.dumps(dict(status='passed', checks=checks, paid_api_requests=0), indent=2))


if __name__ == '__main__':
    main()
