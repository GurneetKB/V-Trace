import numpy as np

from vtrace.som import VehicleSOM


def _clusters(n_per=15, k=3, dim=64, seed=0):
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(k, dim)) * 5
    X = np.vstack([c + rng.normal(size=(n_per, dim)) for c in centres])
    return X, np.repeat(np.arange(k), n_per)


def test_som_groups_clusters_without_labels():
    X, labels = _clusters()
    som = VehicleSOM(n_components=8).fit(X)
    assert som.purity(X, labels) > 0.8
    assert som.u_matrix().shape == (som.grid, som.grid)


def test_prefilter_keeps_same_cluster_and_drops_others():
    X, labels = _clusters()
    som = VehicleSOM(n_components=8).fit(X)
    mask = som.prefilter(X[0], X, radius=0)
    assert mask.shape == (len(X),) and mask[0]
    assert (labels[mask] == labels[0]).mean() > 0.8
