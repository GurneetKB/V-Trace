"""Evaluate the pretrained FastReID VeRi-776 checkpoint on the official VeRi-776 query/test split (no training).

Standard protocol: each of the 1,678 query images is ranked against the 11,579 test images; gallery images of the
same vehicle from the same camera are ignored. Reports Rank-1 / Rank-5 / mAP and the similarity of same- and
different-vehicle pairs (used to choose config.MATCH_THRESHOLD).

    python scripts/eval_veri.py            # VeRi in config.VERI_DIR; ~20 min on a laptop CPU
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from tqdm import tqdm

from vtrace import config, fastreid


def embed_all(model, paths, batch=64):
    out = []
    for i in tqdm(range(0, len(paths), batch), desc="embedding"):
        out.append(fastreid.embed(model, [cv2.imread(str(p)) for p in paths[i:i + batch]], batch=batch))
    return np.concatenate(out)


def main():
    query = sorted((config.VERI_DIR / "image_query").glob("*.jpg"))
    gallery = sorted((config.VERI_DIR / "image_test").glob("*.jpg"))
    if not query:
        sys.exit(f"VeRi-776 not found in {config.VERI_DIR}")
    model = fastreid.load()
    Q, G = embed_all(model, query), embed_all(model, gallery)
    q_id, q_cam = np.array([p.name[:4] for p in query]), np.array([p.name[5:9] for p in query])
    g_id, g_cam = np.array([p.name[:4] for p in gallery]), np.array([p.name[5:9] for p in gallery])

    r1 = r5 = 0
    aps, same, diff = [], [], []
    rng = np.random.default_rng(0)
    for i in range(len(query)):
        s = G @ Q[i]
        valid = ~((g_id == q_id[i]) & (g_cam == q_cam[i]))
        s, good = s[valid], (g_id == q_id[i])[valid]
        hits = good[np.argsort(-s)]
        r1 += hits[0]
        r5 += hits[:5].any()
        pos = np.flatnonzero(hits)
        aps.append(np.mean((np.arange(len(pos)) + 1) / (pos + 1)))
        same += s[good].tolist()
        diff += rng.choice(s[~good], 50, replace=False).tolist()

    res = {"queries": len(query), "gallery": len(gallery),
           "rank1": 100 * r1 / len(query), "rank5": 100 * r5 / len(query), "mAP": 100 * float(np.mean(aps)),
           "same_vehicle_similarity_percentiles_10_50_90": np.percentile(same, [10, 50, 90]).round(3).tolist(),
           "different_vehicle_similarity_percentiles_50_99_99.9": np.percentile(diff, [50, 99, 99.9]).round(3).tolist()}
    for th in (0.35, 0.4, 0.45, 0.5, 0.55):
        res[f"threshold_{th}"] = {"same_vehicle_kept_%": round(100 * float(np.mean(np.array(same) >= th)), 1),
                                  "different_vehicle_kept_%": round(100 * float(np.mean(np.array(diff) >= th)), 2)}
    print(json.dumps(res, indent=1))
    (config.RESULTS_DIR / "veri_eval.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
