import json

import numpy as np
import pytest

from part5.experiment import evaluate
from part5.histogram import HistogramIndex, METHODS, tokenize
from part5.kmeans import kmeans, lloyd, squared_distances


def test_lloyd_runs_beyond_first_update_and_returns_consistent_centroids():
    points = np.array([[0.], [1.], [2.], [10.], [11.], [12.]])
    result = lloyd(points, [[0.], [1.]])
    assert result.converged and len(result.history) > 1
    np.testing.assert_allclose(np.sort(result.centers[:, 0]), [1, 11])
    assert result.inertia == pytest.approx(4)
    assert all(b['inertia'] <= a['inertia'] + 1e-10 for a, b in zip(result.history, result.history[1:]))
    np.testing.assert_array_equal(result.labels, squared_distances(points, result.centers).argmin(axis=1))
    for label in range(2):
        np.testing.assert_allclose(result.centers[label], points[result.labels == label].mean(axis=0))


def test_empty_clusters_recover_and_seed_is_reproducible():
    points = np.array([[0.], [1.], [2.], [10.], [11.], [12.]])
    repaired = lloyd(points, [[0.], [0.], [12.]])
    assert repaired.empty_repairs and repaired.converged
    assert np.bincount(repaired.labels, minlength=3).min() > 0
    first, second = kmeans(points, 2, seed=542), kmeans(points, 2, seed=542)
    np.testing.assert_array_equal(first.centers, second.centers)
    assert first.inertia == pytest.approx(4)


@pytest.mark.parametrize('points,k', [([[0], [0]], 2), ([[np.nan], [1]], 1), ([], 1), ([[1], [2]], 3)])
def test_invalid_clustering_input_fails_explicitly(points, k):
    with pytest.raises(ValueError):kmeans(points, k)


@pytest.fixture
def histogram():
    return HistogramIndex(['tuning', 'optimization', 'and', 'manual'],
        [[1., 0.], [0., 1.], [-1., 0.], [.9, .1]], [[1., 0.], [0., 1.]],
        [dict(text='tuning tuning optimization', page=1, chunk_id='a'),
         dict(text='manual and', page=2, chunk_id='b')])


def test_required_histogram_counts_repeated_words_and_reports_unknowns(histogram):
    np.testing.assert_allclose(histogram.matrices['hard_histogram'][0], [2 / 3, 1 / 3])
    vector, coverage = histogram.query_features('tuning unknownterm')
    np.testing.assert_allclose(vector, [.5, 0])
    assert coverage['known_tokens'] == 1 and coverage['tokens'] == 2
    for method in METHODS:
        assert not histogram.search('qzxvplmn', method)[0]
        assert not histogram.search('and the of', method)[0]
    assert tokenize('simu-\nlation S11 RF 100') == ['simulation', 's11', 'rf']


def test_weighting_keeps_query_and_document_in_one_fitted_space(histogram):
    before = histogram.idf.copy()
    for method in ['hard_histogram', 'stopword_histogram', 'tfidf_hellinger']:
        query, _ = histogram.query_features(histogram.documents[0]['text'], method)
        np.testing.assert_allclose(query, histogram.matrices[method][0])
    weighted = histogram.matrices['tfidf_hellinger']
    np.testing.assert_allclose(np.square(weighted).sum(axis=1), 1)
    histogram.search('unknown tuning tuning', 'hybrid_tfidf', alpha=.25)
    np.testing.assert_array_equal(before, histogram.idf)
    with pytest.raises(ValueError):histogram.search('tuning', 'hybrid_tfidf', alpha=2)


def test_saved_features_reload_identically_and_tampering_is_rejected(histogram, tmp_path):
    target = tmp_path / 'index'
    histogram.save(target)
    restored = HistogramIndex.load(target)
    for method in METHODS:
        np.testing.assert_allclose(histogram.scores('tuning manual', method)[0],
                                   restored.scores('tuning manual', method)[0])
    path = target / 'documents.json'
    path.write_text(json.dumps([dict(text='tampered')]))
    with pytest.raises(ValueError, match='checksum'):HistogramIndex.load(target)


def test_metrics_count_failed_questions_and_use_first_relevant_rank():
    class FixedIndex:
        def search(self, *args, **kwargs):
            return [dict(document=dict(page=p, chunk_id=str(p)), score=1.) for p in [1, 2, 7]], {}
    questions = [dict(id='one', question='first', relevant_pages=[7]),
                 dict(id='two', question='second', relevant_pages=[8])]
    metrics, _ = evaluate(FixedIndex(), questions, 'hard_histogram')
    assert metrics['hit_at_1'] == 0
    assert metrics['hit_at_3'] == .5
    assert metrics['hit_at_5'] == .5
    assert metrics['mrr_at_10'] == pytest.approx(1 / 6)
