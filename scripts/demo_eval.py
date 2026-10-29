"""Measure cross-camera Re-ID and path tracing on the demo cameras, and pick good demo vehicles.

camA_west / camB_centre / camC_east are three zones of the same 1080p clip (scripts/prepare_demo_clips.py), so a
reference identity for every vehicle can be obtained by tracking the *uncropped* clip and mapping each zone
tracklet back onto it (box IoU in full-frame coordinates, majority vote). This is pseudo ground truth: it inherits
the reference tracker's own mistakes, which is stated in the report.

    python scripts/demo_eval.py            # after the four cameras are processed (app tab 1 or build_index.py)

Writes results/demo_eval.json and prints the best demo vehicles (full A->B->C paths traced correctly).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from vtrace import config, reid
from vtrace.index import VehicleIndex
from scripts.prepare_demo_clips import RAW, Y0, ZONES

START_FRAME = 25                 # prepare_demo_clips skips the first 1.0 s (25 fps)
REF_STRIDE = 2
REF_CACHE = config.CACHE_DIR / "demo_reference_tracks.json"
GAP_S = 10                       # the app's default time window when the cameras share a clock
MIN_SCORE = 0.5                  # the app's default minimum match score for the suggested route


def reference_tracks():
    """Track the uncropped clip once (high resolution) -> {raw_frame: [(ref_id, box)]}."""
    if REF_CACHE.exists():
        data = json.loads(REF_CACHE.read_text())
        return {int(k): v for k, v in data.items()}
    from ultralytics import YOLO
    model, cap, out, i = YOLO(config.YOLO_WEIGHTS), cv2.VideoCapture(str(RAW / "ljubljana_a.webm")), {}, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % REF_STRIDE == 0:
            r = model.track(f, persist=True, classes=list(config.VEHICLE_CLASSES), conf=config.DET_CONF,
                            tracker=config.TRACKER_CFG, imgsz=1280, verbose=False)[0]
            if r.boxes.id is not None:
                out[i] = [(int(t), [float(v) for v in b]) for b, t in zip(r.boxes.xyxy.tolist(), r.boxes.id.int().tolist())]
        i += 1
    REF_CACHE.write_text(json.dumps(out))
    return out


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def assign_ids(tracklets, ref):
    """Reference id for each zone tracklet (None when the mapping is unreliable)."""
    for t in tracklets:
        x0 = ZONES[t["video"]][0]
        votes, ious = Counter(), []
        for f, (x1, y1, x2, y2) in zip(t["frames"], t["boxes"]):
            raw_f = f + START_FRAME
            raw_f -= raw_f % REF_STRIDE
            box = (x1 + x0, y1 + Y0, x2 + x0, y2 + Y0)
            best = max(((iou(box, b), rid) for rid, b in ref.get(raw_f, [])), default=(0, None))
            if best[0] > 0.3:
                votes[best[1]] += 1
                ious.append(best[0])
        rid, n = votes.most_common(1)[0] if votes else (None, 0)
        t["ref_id"] = rid if n >= max(2, 0.5 * len(t["frames"])) else None
        t["purity"] = n / max(sum(votes.values()), 1)          # share of matched boxes on the majority vehicle


def strip(tracklets, fname, captions, h=220):
    """Side-by-side crops (first crop of each tracklet) with captions -> results/<fname>."""
    tiles = []
    for t, cap in zip(tracklets, captions):
        im = cv2.imread(t["crop_paths"][0])
        im = cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h))
        tw = cv2.getTextSize(cap, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0][0] + 12
        if tw > im.shape[1]:                                   # widen the tile so the caption fits
            pad = np.full((h, tw - im.shape[1], 3), 255, np.uint8)
            im = np.hstack([pad[:, :pad.shape[1] // 2], im, pad[:, pad.shape[1] // 2:]])
        bar = np.full((40, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, cap, (6, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (32, 24, 17), 2)
        tiles.append(np.vstack([im, bar]))
        tiles.append(np.full((h + 40, 16, 3), 255, np.uint8))
    cv2.imwrite(str(config.RESULTS_DIR / fname), np.hstack(tiles[:-1]))


def ap(ranked_ok, n_pos):
    hits, s = 0, 0.0
    for k, ok in enumerate(ranked_ok, 1):
        if ok:
            hits += 1
            s += hits / k
    return s / max(n_pos, 1)


def main():
    index = VehicleIndex.load()
    cams = list(ZONES)
    videos = cams + ["camD_other_road"]
    missing = [v for v in videos if v not in index.videos()]
    if missing:
        sys.exit(f"Process these videos first: {missing}")
    view = index.subset(videos)
    zone_ts = [t for t in view.tracklets if t["video"] in ZONES]
    if "boxes" not in zone_ts[0]:
        sys.exit("These videos were indexed by an older version; re-process them (app tab 1 or build_index.py).")
    assign_ids(zone_ts, reference_tracks())
    by_id = defaultdict(list)
    for t in zone_ts:
        if t["ref_id"] is not None:
            by_id[t["ref_id"]].append(t)
    rf = reid.load_rf()

    results, demo = {}, []
    for setting, gap in (("window", GAP_S), ("no_window", None)):
        results[setting] = {}
        for method in reid.METHODS:
            r1 = r5 = maps = n = 0
            added = correct = truth = found = hit1 = hit3 = 0
            for t in zone_ts:
                if t["ref_id"] is None:
                    continue
                true_vids = {u["video"] for u in by_id[t["ref_id"]] if u["video"] != t["video"]}
                if not true_vids:
                    continue
                hits = reid.reid_search(view, t, method, rf, top_k=10_000, max_gap_s=gap)
                ok = [h[1].get("ref_id") == t["ref_id"] and h[1]["video"] in ZONES for h in hits]
                n_pos = sum(1 for u in by_id[t["ref_id"]] if u["video"] != t["video"])
                r1 += bool(ok) and ok[0]; r5 += any(ok[:5]); maps += ap(ok, n_pos); n += 1
                # suggested route (automatic): precision of its steps, recall of the true cameras
                path = reid.trace_path(view, t, method, rf, min_score=MIN_SCORE, max_gap_s=gap)
                steps = [p for _, p in path if p["uid"] != t["uid"]]
                good = [p for p in steps if p.get("ref_id") == t["ref_id"]]
                added += len(steps); correct += len(good)
                truth += len(true_vids); found += len({p["video"] for p in good})
                # interactive confirmation: is the true sighting first / among the 3 shown for each camera?
                cams = reid.camera_candidates(view, [t], method, rf, gap, k=3)
                for v in true_vids:
                    ids = [c.get("ref_id") for _, c in cams.get(v, [])]
                    hit1 += bool(ids) and ids[0] == t["ref_id"]
                    hit3 += t["ref_id"] in ids
                if setting == "window" and method == "random forest" and len(good) == len(steps) == len(true_vids) == 2:
                    demo.append((t, path))
            results[setting][method] = {"queries": n, "Rank-1": 100 * r1 / n, "Rank-5": 100 * r5 / n,
                                        "mAP": 100 * maps / n,
                                        "route_precision": 100 * correct / max(added, 1),
                                        "route_recall": 100 * found / truth,
                                        "camera_hit@1": 100 * hit1 / truth, "camera_hit@3": 100 * hit3 / truth}
            print(f"{setting:9s} {method:16s} " + "  ".join(f"{k} {v:.1f}" for k, v in results[setting][method].items()))

    mapped = [t for t in zone_ts if t["ref_id"] is not None]
    per_cam = Counter((t["ref_id"], t["video"]) for t in mapped)
    tracking = {"clean_tracklets_%": 100 * np.mean([t["purity"] >= 0.95 for t in mapped]),
                "mean_purity": float(np.mean([t["purity"] for t in mapped])),
                "tracklets_per_vehicle_per_camera": float(np.mean(list(per_cam.values()))),
                "unmapped_tracklets_%": 100 * (1 - len(mapped) / len(zone_ts))}
    print("tracking:", {k: round(v, 2) for k, v in tracking.items()})
    n_multi = sum(1 for ts in by_id.values() if len({t['video'] for t in ts}) >= 2)
    n_all3 = sum(1 for ts in by_id.values() if len({t['video'] for t in ts}) == 3)
    summary = {"tracklets": {v: sum(t["video"] == v for t in view.tracklets) for v in videos},
               "zone_tracklets_with_reference_id": sum(t["ref_id"] is not None for t in zone_ts),
               "vehicles_in_2plus_cameras": n_multi, "vehicles_in_all_3": n_all3, "tracking": tracking,
               "time_window_s": GAP_S, "min_path_score": MIN_SCORE,
               "methods": results["window"], "methods_no_window": results["no_window"]}
    print(json.dumps({k: v for k, v in summary.items() if not k.startswith("methods")}, indent=1))

    demo.sort(key=lambda d: -min(d[1][i][1]["n_obs"] for i in range(len(d[1]))))
    seen, picks = set(), []
    for t, path in demo:
        if t["ref_id"] in seen:
            continue
        seen.add(t["ref_id"])
        picks.append({"query": t["uid"], "colour": config.COLORS[int(np.argmax(t["color_probs"]))],
                      "type": config.TYPES[int(np.argmax(t["type_probs"]))] if t["type_probs"].max() > 0 else "-",
                      "class": t["yolo_class"],
                      "path": [(p["uid"], round(s, 2), round(p["start_t"], 1), round(p["end_t"], 1)) for s, p in path]})
    summary["demo_vehicles"] = picks[:12]
    if demo:
        strip([p for _, p in demo[0][1]], "demo_path_example.jpg",
              [f"{p['camera']} {p['start_t']:.0f}-{p['end_t']:.0f}s" for _, p in demo[0][1]])
    fails = [t for t in zone_ts if t["ref_id"] is not None and any(u["video"] != t["video"] for u in by_id[t["ref_id"]])]
    for t in fails:
        top = reid.reid_search(view, t, "random forest", rf, top_k=1)
        if top and top[0][1].get("ref_id") != t["ref_id"]:
            truth = next(u for u in by_id[t["ref_id"]] if u["video"] != t["video"])
            strip([t, top[0][1], truth], "demo_failure_example.jpg",
                  ["query " + t["camera"], f"wrong #1 {top[0][1]['camera']} ({top[0][0]:.2f})", "true match " + truth["camera"]])
            summary["failure_example"] = {"query": t["uid"], "wrong_top1": top[0][1]["uid"], "truth": truth["uid"],
                                          "score": round(top[0][0], 2)}
            break
    for p in picks[:12]:
        print(p)
    (config.RESULTS_DIR / "demo_eval.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
