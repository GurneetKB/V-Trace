"""Scripted Describe -> Search -> Confirm -> Re-identify run on the current index, saved as report evidence.

    python scripts/demo_walkthrough.py --color white --type estate --cue "sticker / decal" --confirm-video camA_main_road

Writes results/demo/: walkthrough.md, stage1.jpg, stage2.jpg and one tracklet contact sheet per video
(for the manual tracking check).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from vtrace import config, reid, search
from vtrace.index import VehicleIndex
from vtrace.video import fmt_time

OUT = config.RESULTS_DIR / "demo"
TILE = (200, 150)


def tile(path, lines):
    img = cv2.resize(cv2.imread(path), TILE)
    pad = np.full((18 * len(lines) + 6, TILE[0], 3), 255, np.uint8)
    for i, text in enumerate(lines):
        cv2.putText(pad, text[:30], (4, 16 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    return np.vstack([img, pad])


def grid(tiles, cols=6):
    h = max(t.shape[0] for t in tiles)
    tiles = [np.vstack([t, np.full((h - t.shape[0], TILE[0], 3), 255, np.uint8)]) for t in tiles]
    tiles += [np.full_like(tiles[0], 255)] * (-len(tiles) % cols)
    return np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])


def label(t):
    c = config.COLORS[int(np.argmax(t["color_probs"]))]
    ty = config.TYPES[int(np.argmax(t["type_probs"]))] if np.max(t["type_probs"]) > 0 else t["yolo_class"]
    return f"{c} {ty}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color"), ap.add_argument("--type"), ap.add_argument("--plate")
    ap.add_argument("--cue", action="append", default=[])
    ap.add_argument("--confirm-video", help="confirm the best Stage-1 candidate from this video")
    ap.add_argument("--method", default="random forest", choices=reid.METHODS)
    args = ap.parse_args()

    index = VehicleIndex.load()
    if not len(index):
        sys.exit("Index is empty - process videos first (app tab 1 or scripts/build_index.py).")
    OUT.mkdir(parents=True, exist_ok=True)
    md = ["# V-Trace demo walkthrough", "",
          f"Index: {len(index)} tracklets from {', '.join(index.videos())}", ""]

    # tracklet contact sheets for the manual tracking check
    for v in index.videos():
        ts = [t for t in index.tracklets if t["video"] == v]
        cv2.imwrite(str(OUT / f"tracklets_{v}.jpg"),
                    grid([tile(t["crop_paths"][0], [f"track {t['track_id']} ({t['n_obs']} det)", label(t)]) for t in ts], 8))
        md.append(f"- `{v}`: {len(ts)} tracklets, contact sheet `tracklets_{v}.jpg`")

    # Stage 1
    query = dict(color=args.color, vtype=args.type, plate=args.plate, cues=args.cue)
    s1 = search.describe_search(index, **query, top_k=12)
    md += ["", "## Stage 1 - description search", "",
           f"Query: {', '.join(f'{k}={v}' for k, v in query.items() if v) or '(none)'}", "",
           "| # | tracklet | camera | time | label | score | evidence |", "|---|---|---|---|---|---|---|"]
    for i, (score, t, ev) in enumerate(s1, 1):
        md.append(f"| {i} | {t['uid']} | {t['camera']} | {fmt_time(t['start_t'])}-{fmt_time(t['end_t'])} | {label(t)} | "
                  f"{score:.2f} | {', '.join(f'{k} {v:.2f}' for k, v in ev.items())} |")
    cv2.imwrite(str(OUT / "stage1.jpg"), grid([tile(t["crop_paths"][len(t["crop_paths"]) // 2],
                                                     [f"#{i} {s:.2f} {t['camera'][:14]}", label(t)])
                                                for i, (s, t, _) in enumerate(s1, 1)]))

    # Confirm + Stage 2
    pool = [r for r in s1 if not args.confirm_video or r[1]["video"] == args.confirm_video]
    if not pool:
        sys.exit("No Stage-1 candidate in the requested video.")
    q = pool[0][1]
    rf = reid.load_rf()
    method = args.method if (rf or args.method != "random forest") else "weighted fusion"
    s2 = reid.reid_search(index, q, method, rf, top_k=10)
    md += ["", "## Confirm", "", f"Confirmed **{q['uid']}** ({label(q)}, {fmt_time(q['start_t'])}-{fmt_time(q['end_t'])})",
           "", f"## Stage 2 - cross-video Re-ID ({method})", "",
           "| # | tracklet | camera | best view | label | score | app_cos | clip_cos | colour | type |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for i, (score, t, f) in enumerate(s2, 1):
        md.append(f"| {i} | {t['uid']} | {t['camera']} | {fmt_time(t['best_t'])} | {label(t)} | {score:.2f} | "
                  f"{f['app_cos']:.2f} | {f['clip_cos']:.2f} | {f['color_agree']:.2f} | {f['type_agree']:.2f} |")
    tiles = [tile(q["crop_paths"][len(q["crop_paths"]) // 2], ["QUERY (confirmed)", q["camera"][:24]])]
    tiles += [tile(t["crop_paths"][len(t["crop_paths"]) // 2], [f"#{i} {s:.2f} {t['camera'][:14]}", label(t)])
              for i, (s, t, _) in enumerate(s2, 1)]
    cv2.imwrite(str(OUT / "stage2.jpg"), grid(tiles))

    (OUT / "walkthrough.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
