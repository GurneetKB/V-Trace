"""Stage 2 - confirmed-candidate cross-camera re-identification.

For a query tracklet and each candidate tracklet we compute a pairwise evidence vector
(appearance, colour, type, plate, cue and track-level features) and turn it into a score with
  * appearance-only   - CNN embedding cosine (baseline)
  * learned metric    - cosine after an LDA projection learned from VeRi identities (vtrace/metric.py)
  * weighted fusion   - transparent hand-set weights (baseline)
  * random forest     - supervised same/different-vehicle classifier (ensemble)
"""
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from . import config, metric, plate as plate_utils

METHODS = ["appearance only", "learned metric", "weighted fusion", "random forest"]


def pair_features(a, b):
    plate_ok = bool(a.get("plate")) and bool(b.get("plate"))
    hist_a, hist_b = a["hsv_hist"], b["hsv_hist"]
    cue_a, cue_b = np.asarray(a["cue_probs"]), np.asarray(b["cue_probs"])
    app_cos = float(a["app_emb"] @ b["app_emb"])
    ma, mb = metric.ensure(a), metric.ensure(b)
    return {
        "metric_cos": float(ma @ mb) if ma is not None and mb is not None else app_cos,
        "app_cos": app_cos,
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
MONOTONIC = {"metric_cos": 1, "app_cos": 1, "clip_cos": 1, "color_hist": 1, "color_agree": 1, "type_agree": 1, "plate_sim": 1,
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
    if method == "learned metric":
        return np.array([f["metric_cos"] for f in feats])
    if method in config.PAIR_FEATURES:            # single-cue ablation
        return np.array([f[method] for f in feats])
    if method == "random forest" and rf is not None:
        return rf.predict_proba(to_matrix(feats))[:, 1]
    if method in ("weighted fusion", "random forest"):  # RF falls back to fusion until trained
        return np.array([weighted_fusion(f) for f in feats])
    raise ValueError(method)


def reid_search(index, query, method="random forest", rf=None, use_som=False, som_radius=1,
                include_same_video=False, top_k=20, max_gap_s=None):
    """Rank tracklets in the other videos by likelihood of being the confirmed query vehicle.
    `max_gap_s` (videos sharing a clock) drops candidates further than that many seconds from the query."""
    cands = [t for t in index.tracklets
             if t["uid"] != query["uid"] and (include_same_video or t["video"] != query["video"])
             and (max_gap_s is None or _gap(t, query) <= max_gap_s)]
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


def camera_candidates(index, members, method="random forest", rf=None, max_gap_s=None, k=3, skip_videos=()):
    """Top-k candidates in every other camera, each scored against ALL known sightings of the vehicle (`members`,
    best score wins). Returns {video: [(score, tracklet), ...]} with the best first."""
    member_videos = {m["video"] for m in members}
    out = {}
    for video in sorted({t["video"] for t in index.tracklets} - member_videos - set(skip_videos)):
        cands = [t for t in index.tracklets if t["video"] == video]
        if max_gap_s is not None:
            cands = [c for c in cands if min(_gap(c, m) for m in members) <= max_gap_s]
        if not cands:
            continue
        scores = np.max([score_pairs([pair_features(m, c) for c in cands], method, rf) for m in members], axis=0)
        order = np.argsort(-scores)[:k]
        out[video] = [(float(scores[i]), cands[i]) for i in order]
    return out


def trace_path(index, query, method="random forest", rf=None, min_score=0.5, max_gap_s=None, margin=0.1):
    """Suggest the confirmed vehicle's route: at most one sighting per other camera, in time order.

    Greedy path growing: candidates are scored against *all* sightings already on the path, so a neighbouring
    camera helps bridge two cameras whose views differ a lot (far/small vs near/large). A camera's best candidate
    joins only if it scores at least `min_score` AND beats that camera's runner-up by `margin` (an ambiguity test,
    like Lowe's ratio test: two similar cars close in time are left for the human to decide). The strongest such
    camera joins first, then the rest are re-scored. `max_gap_s` rejects sightings too far in time from the path
    (only meaningful when the videos share a clock). Returns [(score, tracklet)]; the query has score 1.0.
    """
    path = [(1.0, query)]
    skip = set()
    while True:
        cams = camera_candidates(index, [t for _, t in path], method, rf, max_gap_s, k=2, skip_videos=skip)
        ok = {v: c for v, c in cams.items()
              if c[0][0] >= min_score and (len(c) == 1 or c[0][0] - c[1][0] >= margin)}
        if not ok:
            break
        video = max(ok, key=lambda v: ok[v][0][0])
        path.append(ok[video][0])
        skip.add(video)
    return sorted(path, key=lambda st: st[1]["start_t"])


def _gap(a, b):
    """Seconds between two tracklets' time spans (0 if they overlap)."""
    return max(0.0, a["start_t"] - b["end_t"], b["start_t"] - a["end_t"])
