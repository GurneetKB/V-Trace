"""Supervised metric learning for re-identification.

The ImageNet ResNet-50 and CLIP embeddings describe "a car" well but were never trained to tell two cars apart.
A linear projection learned from labelled vehicle identities (VeRi-776 training split) fixes much of that:
standardise [ResNet | CLIP] (2560-d) -> PCA (256) -> Linear Discriminant Analysis, which keeps the directions that
separate identities and suppresses within-identity variation (viewpoint, scale, lighting). Cosine similarity in the
projected space is the `metric_cos` evidence feature.

Trained by scripts/train_eval.py (models/metric_lda.joblib). Without the model, `metric_cos` falls back to the
ResNet cosine, so everything still runs.
"""
import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config

_MODEL = []                                   # lazily loaded [model or None]


def _x(tracklets):
    return np.hstack([np.stack([t["app_emb"] for t in tracklets]), np.stack([t["clip_emb"] for t in tracklets])])


def _l2(x):
    return (x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def fit(tracklets, n_pca=256):
    ids = [t["vehicle_id"] for t in tracklets]
    n_pca = min(n_pca, len(tracklets) - 1)
    return make_pipeline(StandardScaler(), PCA(n_pca, random_state=0), LinearDiscriminantAnalysis()).fit(_x(tracklets), ids)


def embed(model, tracklets):
    """Store the L2-normalised projection as t['metric_emb']."""
    for t, e in zip(tracklets, _l2(model.transform(_x(tracklets)))):
        t["metric_emb"] = e


def out_of_fold(train, folds=5):
    """Projections for TRAIN tracklets from models that never saw that vehicle (avoids a stacking leak, as for
    the attribute probes: in-sample projections would make same-vehicle pairs look unrealistically similar)."""
    from sklearn.model_selection import GroupKFold
    groups = np.array([t["vehicle_id"] for t in train])
    for fit_idx, pred_idx in GroupKFold(n_splits=folds).split(np.zeros(len(train)), groups, groups):
        embed(fit([train[i] for i in fit_idx]), [train[i] for i in pred_idx])


def load():
    if not _MODEL:
        _MODEL.append(joblib.load(config.METRIC_PATH) if config.METRIC_PATH.exists() else None)
    return _MODEL[0]


def ensure(t):
    """Projection for one tracklet, computed on first use from its stored embeddings (None if no model)."""
    if t.get("metric_emb") is None:
        model = load()
        if model is None:
            return None
        embed(model, [t])
    return t["metric_emb"]
