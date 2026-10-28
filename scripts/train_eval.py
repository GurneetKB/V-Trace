"""Train the matching models on VeRi-776 and run every experiment from the proposal.

    python scripts/train_eval.py                 # default subset (fast-ish on CPU)
    python scripts/train_eval.py --train-ids 300 --test-ids 200

Outputs
  models/attr_probe.joblib     supervised colour/type linear probe on CLIP embeddings
  models/rf_matcher.joblib     Random Forest same/different-vehicle matcher (used by the app)
  results/metrics.json         all numbers below; results/*.png plots

Experiments
  1. Attribute recognition: CLIP zero-shot vs supervised linear probe (colour, type accuracy)
  2. Stage-1 description retrieval (colour/type/partial plate queries) - Rank-1/5, mAP
  3. Cross-camera Re-ID: single cues vs weighted fusion vs Random Forest - Rank-1/5, mAP
  4. Plate robustness: clear -> partial -> blurred -> hidden
  5. Unsupervised SOM: cluster purity and candidate pre-filtering

VeRi-776 has no plate *text*, so each vehicle gets a synthetic plate string which is then
degraded per observation. This isolates the question "what happens when plate evidence fails?".
"""
import argparse
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import joblib
import matplotlib
import numpy as np
from sklearn.linear_model import LogisticRegression
from tqdm import tqdm

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vtrace import config, plate as plate_utils, reid, search, veri
from vtrace.som import VehicleSOM

LEVELS = ["clear", "partial", "blurred", "hidden"]


# ---------------------------------------------------------------- helpers
def describe_tracklets(tracklets, fe, cache_name):
    cache = config.CACHE_DIR / cache_name
    if cache.exists():
        print(f"Loading cached features {cache.name}")
        return joblib.load(cache)
    for t in tqdm(tracklets, desc=f"Describing {cache_name}"):
        crops = [cv2.imread(p) for p in t["crop_paths"]]
        t.update(fe.describe(crops, read_plate=False))
        t["color_probs_zs"], t["type_probs_zs"] = t["color_probs"], t["type_probs"]
    joblib.dump(tracklets, cache)
    return tracklets


def ranking_metrics(score_lists):
    """score_lists: list of (scores array, relevant bool array). Returns Rank-1, Rank-5, mAP (%)."""
    r1 = r5 = ap_sum = 0.0
    for scores, rel in score_lists:
        order = np.argsort(-scores)
        rel_sorted = rel[order]
        hits = np.where(rel_sorted)[0]
        r1 += hits[0] < 1
        r5 += hits[0] < 5
        precision = np.arange(1, len(hits) + 1) / (hits + 1)
        ap_sum += precision.mean()
    n = len(score_lists)
    return {"rank1": round(100 * float(r1) / n, 2), "rank5": round(100 * float(r5) / n, 2),
            "mAP": round(100 * float(ap_sum) / n, 2)}


def set_plates(tracklets, level_fn, seed):
    for i, t in enumerate(tracklets):
        rng = random.Random(f"{seed}-{t['uid']}")
        t["plate"] = plate_utils.degrade(t["true_plate"], level_fn(rng), rng)


def update_plate_feats(feats, q, gallery):
    for f, g in zip(feats, gallery):
        ok = bool(q["plate"]) and bool(g["plate"])
        f["plate_avail"] = float(ok)
        f["plate_sim"] = plate_utils.similarity(q["plate"], g["plate"]) if ok else 0.0


# ---------------------------------------------------------------- experiments
def attribute_experiment(train, test, results):
    probe, out = {}, {}
    for key, label, vocab in (("color", "color_label", config.COLORS), ("type", "type_label", config.TYPES)):
        tr = [t for t in train if t[label] is not None]
        te = [t for t in test if t[label] is not None]
        if not tr or not te:
            print(f"No {key} labels found - skipping {key} probe.")
            continue
        clf = LogisticRegression(max_iter=3000, C=2.0)
        clf.fit(np.stack([t["clip_emb"] for t in tr]), [t[label] for t in tr])
        probe[key] = clf
        y = np.array([t[label] for t in te])
        zs = np.array([np.argmax(t[f"{key}_probs_zs"]) for t in te])
        pr = clf.predict(np.stack([t["clip_emb"] for t in te]))
        out[key] = {"zero_shot_acc": 100 * float((zs == y).mean()),
                    "linear_probe_acc": 100 * float((pr == y).mean()), "n_test": len(te)}
        print(f"{key}: zero-shot {out[key]['zero_shot_acc']:.1f}%  probe {out[key]['linear_probe_acc']:.1f}%")
    if len(probe) == 2:
        joblib.dump(probe, config.ATTR_PROBE_PATH)
        for t in test:  # from now on use the supervised attribute probabilities
            for key, n in (("color", len(config.COLORS)), ("type", len(config.TYPES))):
                p = np.zeros(n)
                p[probe[key].classes_] = probe[key].predict_proba(t["clip_emb"][None])[0]
                t[f"{key}_probs"] = p
        out_of_fold_attributes(train)
    results["attributes"] = out


def out_of_fold_attributes(train, folds=5):
    """Attribute probabilities for TRAIN tracklets from probes that never saw that vehicle.

    The Random Forest is trained on train pairs. If their colour/type probabilities came from a probe fitted on
    those same vehicles they would be near-perfect, the RF would over-trust them, and it would rank badly on
    unseen vehicles (a stacking leak). Out-of-fold predictions, grouped by vehicle identity, give the training
    features the same noise level as at test time.
    """
    from sklearn.model_selection import GroupKFold
    X = np.stack([t["clip_emb"] for t in train])
    groups = np.array([t["vehicle_id"] for t in train])
    for key, label, n in (("color", "color_label", len(config.COLORS)), ("type", "type_label", len(config.TYPES))):
        y = np.array([-1 if t[label] is None else t[label] for t in train])
        probs = np.zeros((len(train), n))
        for fit_idx, pred_idx in GroupKFold(n_splits=folds).split(X, y, groups):
            fit_idx = fit_idx[y[fit_idx] >= 0]
            clf = LogisticRegression(max_iter=3000, C=2.0).fit(X[fit_idx], y[fit_idx])
            probs[np.ix_(pred_idx, clf.classes_)] = clf.predict_proba(X[pred_idx])
        for t, p in zip(train, probs):
            t[f"{key}_probs"] = p
        lab = y >= 0
        print(f"{key}: out-of-fold train accuracy {100 * (probs[lab].argmax(1) == y[lab]).mean():.1f}% (used for RF pairs)")


def build_training_pairs(train, neg_ratio, max_pos, rng):
    by_id = {}
    for t in train:
        by_id.setdefault(t["vehicle_id"], []).append(t)
    pos = [(a, b) for ts in by_id.values() for a, b in itertools.combinations(ts, 2) if a["camera"] != b["camera"]]
    rng.shuffle(pos)
    pos = pos[:max_pos]
    neg = []
    attr = {t["uid"]: (np.argmax(t["color_probs"]), np.argmax(t["type_probs"])) for t in train}
    while len(neg) < neg_ratio * len(pos):
        a, b = rng.sample(train, 2)
        if a["vehicle_id"] == b["vehicle_id"]:
            continue
        # half of the negatives are "hard": same predicted colour and type
        if len(neg) % 2 == 0 or attr[a["uid"]] == attr[b["uid"]]:
            neg.append((a, b))
    feats = [reid.pair_features(a, b) for a, b in pos + neg]
    y = np.array([1] * len(pos) + [0] * len(neg))
    return reid.to_matrix(feats), y


def reid_experiment(test, rf, max_queries, rng, results):
    queries = [q for q in test if any(g["vehicle_id"] == q["vehicle_id"] and g["camera"] != q["camera"] for g in test)]
    rng.shuffle(queries)
    queries = queries[:max_queries]
    print(f"Re-ID: {len(queries)} query tracklets, gallery {len(test)} tracklets")

    base = []  # non-plate features computed once per query
    for q in tqdm(queries, desc="Pair features"):
        gallery = [g for g in test if g["camera"] != q["camera"]]
        base.append((q, gallery, [reid.pair_features(q, g) for g in gallery],
                     np.array([g["vehicle_id"] == q["vehicle_id"] for g in gallery])))

    methods = ["appearance only", "plate_sim", "weighted fusion", "random forest"]
    ablation = [k for k in config.PAIR_FEATURES if k not in ("plate_avail",)]
    out = {}
    for level in LEVELS:
        set_plates(test, lambda r: level, seed=1)
        lists = {m: [] for m in set(methods + ablation)}
        for q, gallery, feats, rel in base:
            update_plate_feats(feats, q, gallery)
            for m in lists:
                lists[m].append((reid.score_pairs(feats, m, rf), rel))
        out[level] = {m: ranking_metrics(v) for m, v in lists.items()}
        print(f"[{level:8s}] " + "  ".join(f"{m}: R1 {out[level][m]['rank1']:.1f} mAP {out[level][m]['mAP']:.1f}"
                                         for m in methods))
    results["reid"] = out
    return base


def som_experiment(test, base, rf, results):
    som = VehicleSOM().fit(np.stack([t["app_emb"] for t in test]))
    embs = np.stack([t["app_emb"] for t in test])
    out = {"grid": som.grid,
           "purity_vehicle_id": som.purity(embs, [t["vehicle_id"] for t in test]),
           "purity_color": som.purity(embs, [t["color_label"] for t in test]),
           "purity_type": som.purity(embs, [t["type_label"] for t in test]),
           "prefilter": {}}
    set_plates(test, lambda r: "hidden", seed=1)
    for radius in (1, 2, 3):
        kept_frac, recall, lists = [], [], []
        for q, gallery, feats, rel in base:
            update_plate_feats(feats, q, gallery)
            mask = som.prefilter(q["app_emb"], np.stack([g["app_emb"] for g in gallery]), radius)
            kept_frac.append(mask.mean())
            recall.append(rel[mask].sum() / rel.sum())
            scores = reid.score_pairs(feats, "random forest", rf)
            scores = np.where(mask, scores, -1.0)       # filtered-out candidates go to the bottom
            lists.append((scores, rel))
        out["prefilter"][f"radius_{radius}"] = {
            "candidates_kept_%": 100 * float(np.mean(kept_frac)),
            "true_match_recall_%": 100 * float(np.mean(recall)),
            **ranking_metrics(lists)}
    results["som"] = out
    print("SOM:", json.dumps(out, indent=1))

    # U-matrix with tracklets coloured by their (true) colour label
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(som.u_matrix().T, cmap="bone_r", origin="lower")
    cmap = {"yellow": "gold", "orange": "orange", "green": "green", "gray": "gray", "red": "red", "blue": "blue",
            "white": "white", "golden": "goldenrod", "brown": "saddlebrown", "black": "black"}
    jit = np.random.default_rng(0)
    for (i, j), t in zip(som.bmus(embs), test):
        c = cmap.get(config.COLORS[t["color_label"]], "k") if t["color_label"] is not None else "k"
        ax.scatter(i + jit.uniform(-.3, .3), j + jit.uniform(-.3, .3), s=12, c=c, edgecolors="k", linewidths=.3)
    ax.set_title("SOM U-matrix (VeRi test tracklets, dot = true colour)")
    fig.tight_layout()
    fig.savefig(config.RESULTS_DIR / "som_umatrix.png", dpi=120)
    plt.close(fig)


def combine(field_scores):
    w = {k: config.SEARCH_WEIGHTS[k] for k in field_scores}
    return sum(w[k] * v for k, v in field_scores.items()) / sum(w.values())


def description_experiment(test, results):
    """Stage 1: query each test vehicle by its true colour/type and a partial plate."""
    set_plates(test, lambda r: r.choice(LEVELS), seed=2)   # realistic mix of plate visibility
    by_id = {}
    for t in test:
        by_id.setdefault(t["vehicle_id"], []).append(t)
    out = {}
    configs = {"colour + type": (True, True, False), "partial plate only": (False, False, True),
               "colour + type + partial plate": (True, True, True)}
    for name, (use_c, use_t, use_p) in configs.items():
        lists = []
        for vid, ts in by_id.items():
            ref = ts[0]
            if ref["color_label"] is None and (use_c or use_t):
                continue
            rng = random.Random(f"q-{vid}")
            kw = dict(color=config.COLORS[ref["color_label"]] if use_c else None,
                      vtype=config.TYPES[ref["type_label"]] if use_t else None,
                      plate=plate_utils.degrade(ref["true_plate"], "partial", rng) if use_p else None)
            scores = np.array([combine(search.field_scores(t, **kw)) for t in test])
            lists.append((scores, np.array([t["vehicle_id"] == vid for t in test])))
        if lists:
            out[name] = ranking_metrics(lists)
            print(f"Description search [{name}]: {out[name]}")
    results["description_search"] = out


def plots(results, rf):
    reid_res = results["reid"]
    methods = ["appearance only", "plate_sim", "weighted fusion", "random forest"]
    labels = {"plate_sim": "plate only"}
    fig, ax = plt.subplots(figsize=(7, 4))
    for m in methods:
        ax.plot(LEVELS, [reid_res[l][m]["mAP"] for l in LEVELS], marker="o", label=labels.get(m, m))
    ax.set_ylabel("mAP (%)"); ax.set_xlabel("plate visibility"); ax.set_title("Plate-degradation robustness")
    ax.legend(); ax.grid(alpha=.3); fig.tight_layout()
    fig.savefig(config.RESULTS_DIR / "plate_robustness.png", dpi=120); plt.close(fig)

    feats = [k for k in config.PAIR_FEATURES if k != "plate_avail"] + ["weighted fusion", "random forest"]
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, level in enumerate(("clear", "hidden")):
        ax.bar(np.arange(len(feats)) + i * 0.4, [reid_res[level][f]["mAP"] for f in feats], 0.4, label=f"plate {level}")
    ax.set_xticks(np.arange(len(feats)) + 0.2, feats, rotation=40, ha="right")
    ax.set_ylabel("mAP (%)"); ax.set_title("Ablation: single cues vs fusion"); ax.legend(); fig.tight_layout()
    fig.savefig(config.RESULTS_DIR / "ablation.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(config.PAIR_FEATURES, rf.feature_importances_)
    ax.set_title("Random Forest feature importance"); fig.tight_layout()
    fig.savefig(config.RESULTS_DIR / "rf_importance.png", dpi=120); plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-ids", type=int, default=150)
    ap.add_argument("--test-ids", type=int, default=100)
    ap.add_argument("--max-queries", type=int, default=300)
    ap.add_argument("--max-pos", type=int, default=6000)
    ap.add_argument("--neg-ratio", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not veri.available():
        sys.exit(f"VeRi-776 not found in {config.VERI_DIR}. See README.md -> 'Benchmark data'.")

    from vtrace.features import FeatureExtractor
    fe = FeatureExtractor(use_ocr=False)
    fe.probe = None  # raw zero-shot attributes; the probe is (re)trained below

    train = describe_tracklets(veri.load_tracklets("train", args.train_ids, seed=args.seed), fe,
                               f"veri_train_{args.train_ids}_s{args.seed}.pkl")
    test = describe_tracklets(veri.load_tracklets("test", args.test_ids, seed=args.seed), fe,
                              f"veri_test_{args.test_ids}_s{args.seed}.pkl")
    print(f"Train: {len(train)} tracklets / {len({t['vehicle_id'] for t in train})} vehicles | "
          f"Test: {len(test)} tracklets / {len({t['vehicle_id'] for t in test})} vehicles (identity-disjoint)")

    rng = random.Random(args.seed)
    plates = {}
    for t in train + test:  # one synthetic plate per vehicle identity
        t["true_plate"] = plates.setdefault(t["vehicle_id"], plate_utils.random_plate(rng))

    results = {"setup": vars(args) | {"n_train_tracklets": len(train), "n_test_tracklets": len(test)}}
    attribute_experiment(train, test, results)

    set_plates(train, lambda r: r.choice(LEVELS), seed=args.seed)  # train RF on mixed plate visibility
    X, y = build_training_pairs(train, args.neg_ratio, args.max_pos, rng)
    print(f"RF training pairs: {int(y.sum())} positive / {int((1 - y).sum())} negative")
    rf = reid.train_rf(X, y, args.seed)
    joblib.dump(rf, config.RF_PATH)
    results["rf_feature_importance"] = dict(zip(config.PAIR_FEATURES, map(float, rf.feature_importances_)))

    description_experiment(test, results)
    base = reid_experiment(test, rf, args.max_queries, rng, results)
    som_experiment(test, base, rf, results)
    plots(results, rf)

    (config.RESULTS_DIR / "metrics.json").write_text(json.dumps(results, indent=2, default=float))
    print(f"\nSaved models to {config.MODELS_DIR} and results to {config.RESULTS_DIR}")


if __name__ == "__main__":
    main()
