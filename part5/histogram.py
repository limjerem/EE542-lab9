"""Required K-bin counts, weighted alternatives and a shared query/document space."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from gensim.parsing.preprocessing import STOPWORDS
import numpy as np

from .kmeans import squared_distances

METHODS = ('hard_histogram', 'stopword_histogram', 'tfidf_hellinger',
           'hybrid_tfidf', 'lexical_tfidf')


def tokenize(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = re.sub(r'(?<=[a-z])-\s*\n\s*(?=[a-z])', '', text)
    return [word for word in re.findall(r'[a-z0-9]+(?:_[a-z0-9]+)*', text)
            if re.search('[a-z]', word)]


def normalize_rows(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms != 0)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HistogramIndex:
    def __init__(self, vocabulary, vectors, centers, documents, metadata=None):
        self.vocabulary = list(vocabulary)
        self.vectors = np.asarray(vectors, dtype=np.float64)
        self.centers = np.asarray(centers, dtype=np.float64)
        self.documents = list(documents)
        self.metadata = metadata or {}
        if (len(set(self.vocabulary)) != len(self.vocabulary)
                or self.vectors.ndim != 2 or len(self.vectors) != len(self.vocabulary)
                or self.centers.ndim != 2 or not len(self.centers)
                or not self.vectors.shape[1] or self.centers.shape[1] != self.vectors.shape[1]
                or not np.isfinite(self.vectors).all() or not np.isfinite(self.centers).all()
                or (np.linalg.norm(self.vectors, axis=1) == 0).any() or not self.documents):
            raise ValueError('Invalid vocabulary, vectors, centers or documents')
        self.word_index = {word: i for i, word in enumerate(self.vocabulary)}
        self.codes = squared_distances(self.vectors, self.centers).argmin(axis=1)
        self.keep = np.array([word not in STOPWORDS for word in self.vocabulary])
        self.counts = np.zeros((len(self.documents), len(self.vocabulary)), dtype=np.float64)
        totals = []
        for i, document in enumerate(self.documents):
            tokens = tokenize(document['text'])
            totals.append(len(tokens))
            for word, count in Counter(tokens).items():
                if word in self.word_index:
                    self.counts[i, self.word_index[word]] = count
        self.totals = np.asarray(totals)
        self.idf = np.log((1 + len(self.documents)) / (1 + (self.counts > 0).sum(axis=0))) + 1
        self.matrices = {method: self._features(self.counts, self.totals, method)
                         for method in METHODS if method != 'hybrid_tfidf'}
        self.normalized = {method: normalize_rows(matrix) for method, matrix in self.matrices.items()}

    def _features(self, counts, totals, method):
        weights = counts.copy()
        if method != 'hard_histogram':
            weights[:, ~self.keep] = 0
        if method in ('tfidf_hellinger', 'lexical_tfidf'):
            nonzero = weights > 0
            weights[nonzero] = 1 + np.log(weights[nonzero])
            weights *= self.idf
        if method == 'lexical_tfidf':
            return weights
        result = np.zeros((len(counts), len(self.centers)), dtype=np.float64)
        np.add.at(result.T, self.codes, weights.T)
        denominator = totals if method == 'hard_histogram' else result.sum(axis=1)
        result = np.divide(result, np.asarray(denominator)[:, None], out=np.zeros_like(result),
                           where=np.asarray(denominator)[:, None] != 0)
        return np.sqrt(result) if method == 'tfidf_hellinger' else result

    def query_features(self, text, method='hard_histogram'):
        if method not in METHODS or method == 'hybrid_tfidf':
            raise ValueError('Select one standalone representation')
        tokens = tokenize(text)
        counts = np.zeros((1, len(self.vocabulary)))
        for word, count in Counter(tokens).items():
            if word in self.word_index:
                counts[0, self.word_index[word]] = count
        feature = self._features(counts, [len(tokens)], method)
        content = [word for word in tokens if word not in STOPWORDS]
        coverage = dict(tokens=len(tokens), known_tokens=int(counts.sum()),
                        content_tokens=len(content),
                        known_content_tokens=sum(word in self.word_index for word in content),
                        unknown_tokens=sorted(set(tokens) - self.word_index.keys()))
        return feature[0], coverage

    def scores(self, text, method='hard_histogram', alpha=0.5):
        if method not in METHODS or not 0 <= alpha <= 1:
            raise ValueError('Unknown method or invalid hybrid weight')
        if method == 'hybrid_tfidf':
            histogram, coverage = self.scores(text, 'tfidf_hellinger')
            lexical, _ = self.scores(text, 'lexical_tfidf')
            return alpha * histogram + (1 - alpha) * lexical, coverage
        vector, coverage = self.query_features(text, method)
        if not coverage['known_content_tokens'] or not np.linalg.norm(vector):
            return np.zeros(len(self.documents)), coverage
        return self.normalized[method] @ (vector / np.linalg.norm(vector)), coverage

    def search(self, text, method='hard_histogram', alpha=0.5, k=5):
        if k < 1:
            raise ValueError('k must be positive')
        scores, coverage = self.scores(text, method, alpha)
        ranking = np.argsort(-scores, kind='stable')[:k]
        matches = [dict(document=self.documents[int(i)], score=float(scores[i]))
                   for i in ranking if scores[i] > 0]
        return matches, coverage

    def save(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        np.savez_compressed(directory / 'encoder.npz', vocabulary=np.asarray(self.vocabulary),
                            vectors=self.vectors, centers=self.centers)
        (directory / 'documents.json').write_text(json.dumps(self.documents, ensure_ascii=False), encoding='utf-8')
        manifest = dict(format_version=1, metadata=self.metadata,
                        hashes={name: sha256(directory / name) for name in ['encoder.npz', 'documents.json']})
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format_version') != 1:
            raise ValueError('Unknown histogram artifact format')
        if set(manifest.get('hashes', {})) != {'encoder.npz', 'documents.json'}:
            raise ValueError('Invalid histogram artifact manifest')
        for name, digest in manifest['hashes'].items():
            if sha256(directory / name) != digest:
                raise ValueError('Histogram artifact checksum mismatch')
        with np.load(directory / 'encoder.npz', allow_pickle=False) as data:
            return cls(data['vocabulary'].tolist(), data['vectors'], data['centers'],
                       json.loads((directory / 'documents.json').read_text(encoding='utf-8')),
                       manifest['metadata'])
