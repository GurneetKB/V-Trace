"""Stage 2 - confirmed-candidate cross-camera re-identification.

For a query tracklet and each candidate tracklet we compute a pairwise evidence vector
(appearance, colour, type, plate, cue and track-level features) and turn it into a score with
  * appearance-only   - CNN embedding cosine (baseline)
  * weighted fusion   - transparent hand-set weights (baseline)
  * random forest     - supervised same/different-vehicle classifier (ensemble)
"""
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from . import config, plate as plate_utils

METHODS = ["appearance only", "weighted fusion", "random forest"]


def pair_features(a, b):
    plate_ok = bool(a.get("plate")) and bool(b.get("plate"))
    hist_a, hist_b = a["hsv_hist"], b["hsv_hist"]
    cue_a, cue_b = np.asarray(a["cue_probs"]), np.asarray(b["cue_probs"])
    return {
        "app_cos": float(a["app_emb"] @ b["app_emb"]),
        "clip_cos": float(a["clip_emb"] @ b["clip_emb"]),
        "color_hist": float(np.minimum(hist_a, hist_b).sum()),
        "color_agree": float(np.dot(a["color_probs"], b["color_probs"])),
        "type_agree": float(np.dot(a["type_probs"], b["type_probs"])),
        "plate_sim": plate_utils.similarity(a["plate"], b["plate"]) if plate_ok else 0.0,
        "plate_avail": float(plate_ok),
        "cue_sim": float(1 - np.abs(cue_a - cue_b).mean()),
        "track_quality": min(a["n_crops"], b["n_crops"]) / config.CROPS_PER_TRACK,
        "track_consist": min(a["consistency"], b["consistency"]),
    }


def to_matrix(feats):
    return np.array([[f[k] for k in config.PAIR_FEATURES] for f in feats], dtype=np.float32)


def weighted_fusion(f):
    w = dict(config.FUSION_WEIGHTS)
    if not f["plate_avail"]:
        w.pop("plate_sim")
    return sum(w[k] * f[k] for k in w) / sum(w.values())


# +1: more similar on this cue must never lower the match score. Without these constraints the forest learned
# non-monotonic splits on VeRi (large viewpoint changes) and ranked worse than appearance alone.
MONOTONIC = {"app_cos": 1, "clip_cos": 1, "color_hist": 1, "color_agree": 1, "type_agree": 1, "plate_sim": 1,
             "plate_avail": 0, "cue_sim": 1, "track_quality": 0, "track_consist": 0}


def train_rf(X, y, seed=0):
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced", n_jobs=-1,
                                random_state=seed, monotonic_cst=[MONOTONIC[k] for k in config.PAIR_FEATURES])
    return rf.fit(X, y)


def load_rf():
    return joblib.load(config.RF_PATH) if config.RF_PATH.exists() else None


def score_pairs(feats, method, rf=None):
    if method == "appearance only":
        return np.array([f["app_cos"] for f in feats])
    if method in config.PAIR_FEATURES:            # single-cue ablation
        return np.array([f[method] for f in feats])
    if method == "random forest" and rf is not None:
        return rf.predict_proba(to_matrix(feats))[:, 1]
    if method in ("weighted fusion", "random forest"):  # RF falls back to fusion until trained
        return np.array([weighted_fusion(f) for f in feats])
    raise ValueError(method)


def reid_search(index, query, method="random forest", rf=None, use_som=False, som_radius=1,
                include_same_video=False, top_k=20):
    """Rank tracklets in the other videos by likelihood of being the confirmed query vehicle."""
    cands = [t for t in index.tracklets
             if t["uid"] != query["uid"] and (include_same_video or t["video"] != query["video"])]
    if not cands:
        return []
    if use_som and index.som is not None:
        keep = index.som.prefilter(query["app_emb"], index.matrix("app_emb", cands), som_radius)
        cands = [c for c, k in zip(cands, keep) if k]
        if not cands:
            return []
    feats = [pair_features(query, c) for c in cands]
    scores = score_pairs(feats, method, rf)
    order = np.argsort(-scores)[:top_k]
    return [(float(scores[i]), cands[i], feats[i]) for i in order]
