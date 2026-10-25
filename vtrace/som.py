"""Unsupervised learning: Self-Organizing Map over vehicle appearance embeddings.

Embeddings are reduced with PCA, then a SOM groups visually similar vehicles
without using identity labels. The map can optionally pre-filter Re-ID candidates
(keep only tracklets mapped near the query's best-matching unit).
"""
import numpy as np
from minisom import MiniSom
from sklearn.decomposition import PCA


class VehicleSOM:
    def __init__(self, n_components=32, grid=None, seed=0):
        self.n_components = n_components
        self.grid = grid
        self.seed = seed

    def fit(self, embs, iters=3000):
        embs = np.asarray(embs, dtype=np.float64)
        n = len(embs)
        self.pca = PCA(n_components=min(self.n_components, n, embs.shape[1]), random_state=self.seed)
        z = self.pca.fit_transform(embs)
        self.scale = np.linalg.norm(z, axis=1).mean() + 1e-12
        z = z / self.scale
        side = self.grid or max(2, int(round(np.sqrt(5 * np.sqrt(n)) / 1.2)))  # Vesanto heuristic
        self.grid = side
        self.som = MiniSom(side, side, z.shape[1], sigma=max(1.0, side / 3), learning_rate=0.5,
                           random_seed=self.seed)
        self.som.pca_weights_init(z) if n >= 2 and z.shape[1] >= 2 else self.som.random_weights_init(z)
        self.som.train_random(z, max(iters, 20 * n), verbose=False)
        return self

    def _z(self, embs):
        return self.pca.transform(np.atleast_2d(np.asarray(embs, dtype=np.float64))) / self.scale

    def bmus(self, embs):
        return [self.som.winner(z) for z in self._z(embs)]

    def prefilter(self, query_emb, cand_embs, radius=1):
        """Boolean mask of candidates whose BMU lies within `radius` (Chebyshev) of the query BMU."""
        qi, qj = self.bmus(query_emb)[0]
        return np.array([max(abs(i - qi), abs(j - qj)) <= radius for i, j in self.bmus(cand_embs)])

    def u_matrix(self):
        return self.som.distance_map()

    def purity(self, embs, labels):
        """Average majority-label fraction per SOM node (how label-homogeneous the clusters are)."""
        from collections import Counter, defaultdict
        nodes = defaultdict(list)
        for b, l in zip(self.bmus(embs), labels):
            nodes[b].append(l)
        total = sum(len(v) for v in nodes.values())
        return sum(Counter(v).most_common(1)[0][1] for v in nodes.values()) / total
