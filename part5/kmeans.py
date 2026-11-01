"""NumPy implementation of k-means++ seeding and Lloyd iterations."""
from dataclasses import dataclass

import numpy as np


def squared_distances(points, centers):
    distances = (np.sum(points * points, axis=1)[:, None]
                 + np.sum(centers * centers, axis=1)[None, :]
                 - 2 * points @ centers.T)
    return np.maximum(distances, 0)


@dataclass
class KMeansResult:
    centers: np.ndarray
    labels: np.ndarray
    inertia: float
    history: list
    converged: bool
    empty_repairs: int
    restart: int = 0


def lloyd(points, initial_centers, max_iter=200):
    """Return nearest-center labels; declare convergence only at a fixed point."""
    points = np.asarray(points, dtype=np.float64)
    centers = np.asarray(initial_centers, dtype=np.float64).copy()
    if (points.ndim != 2 or not len(points) or centers.ndim != 2
            or not len(centers) or points.shape[1] != centers.shape[1]
            or not points.shape[1] or not np.isfinite(points).all()
            or not np.isfinite(centers).all() or max_iter < 1):
        raise ValueError('Expected finite nonempty matrices and a positive iteration limit')
    if len(np.unique(points, axis=0)) < len(centers):
        raise ValueError('K exceeds the number of distinct points')
    history, repairs, converged = [], 0, False
    for iteration in range(max_iter):
        distances = squared_distances(points, centers)
        labels = distances.argmin(axis=1)
        counts = np.bincount(labels, minlength=len(centers))
        errors = distances[np.arange(len(points)), labels]
        # Split a non-singleton cluster at its farthest point to fill each empty bin.
        for empty in np.flatnonzero(counts == 0):
            candidates = np.flatnonzero(counts[labels] > 1)
            chosen = candidates[np.argmax(errors[candidates])]
            counts[labels[chosen]] -= 1
            labels[chosen] = empty
            counts[empty] += 1
            errors[chosen] = 0
            repairs += 1
        updated = np.zeros_like(centers)
        np.add.at(updated, labels, points)
        updated /= counts[:, None]
        inertia = float(np.square(points - updated[labels]).sum())
        nearest = squared_distances(points, updated).argmin(axis=1)
        history.append(dict(iteration=iteration + 1, inertia=inertia,
                            center_shift=float(np.linalg.norm(updated - centers))))
        centers = updated
        # There is no comparison against infinity on the first iteration.
        if np.array_equal(nearest, labels):
            converged = True
            break
    labels = squared_distances(points, centers).argmin(axis=1)
    inertia = float(np.square(points - centers[labels]).sum())
    return KMeansResult(centers, labels, inertia, history, converged, repairs)


def kmeans(points, k, seed=542, n_init=3, max_iter=200):
    """Choose the lowest-SSE run without calling a library clustering routine."""
    points = np.asarray(points, dtype=np.float64)
    if (points.ndim != 2 or not len(points) or not points.shape[1]
            or not np.isfinite(points).all() or not isinstance(k, int)
            or not 1 <= k <= len(points) or n_init < 1 or max_iter < 1):
        raise ValueError('Invalid points, K, restart count or iteration limit')
    if len(np.unique(points, axis=0)) < k:
        raise ValueError('K exceeds the number of distinct points')
    # Centering reduces cancellation in the squared-distance identity.
    offset = points.mean(axis=0)
    centered = points - offset
    rng = np.random.default_rng(seed)
    best = None
    for restart in range(n_init):
        selected = [int(rng.integers(len(points)))]
        closest = squared_distances(centered, centered[selected]).ravel()
        for _ in range(1, k):
            closest[selected] = 0
            probabilities = closest / closest.sum()
            selected.append(int(rng.choice(len(points), p=probabilities)))
            closest = np.minimum(closest, squared_distances(centered, centered[selected[-1:]]).ravel())
        result = lloyd(centered, centered[selected], max_iter=max_iter)
        result.centers += offset
        result.restart = restart
        if best is None or result.inertia < best.inertia:
            best = result
    return best
