"""Measure cross-camera Re-ID and path tracing on the demo cameras, and pick good demo vehicles.

camA_west / camB_centre / camC_east are three zones of the same 1080p clip (scripts/prepare_demo_clips.py), so a
reference identity for every vehicle can be obtained by tracking the *uncropped* clip and mapping each zone
tracklet back onto it (box IoU in full-frame coordinates, majority vote). This is pseudo ground truth: it inherits
the reference tracker's own mistakes, which is stated in the report.

    python scripts/demo_eval.py            # after the four cameras are processed (app tab 1 or build_index.py)

Writes results/demo_eval.json and prints good demo vehicles (seen in exactly the right cameras).
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
    assign_ids(zone_ts, reference_tracks())
    by_id = defaultdict(list)
    for t in zone_ts:
        if t["ref_id"] is not None:
            by_id[t["ref_id"]].append(t)

    r1 = r5 = maps = n = 0
    for t in zone_ts:
        if t["ref_id"] is None or not {u["video"] for u in by_id[t["ref_id"]]} - {t["video"]}:
            continue
        ok = [h[1].get("ref_id") == t["ref_id"] for h in reid.rank(view, t)]   # all other cameras
        n_pos = sum(1 for u in by_id[t["ref_id"]] if u["video"] != t["video"])
        r1 += ok[0]; r5 += any(ok[:5]); maps += ap(ok, n_pos); n += 1
    results = {"queries": n, "Rank-1": 100 * r1 / n, "Rank-5": 100 * r5 / n, "mAP": 100 * maps / n,
               "threshold": config.MATCH_THRESHOLD, "margin": config.MATCH_MARGIN}

    # "where seen" with the app's rule, with and without the real-world time window (curated camera clocks, vtrace/cameras.py)
    demo = []
    for name, gap in (("real_time_window", config.MAX_GAP_S), ("no_time_window", None)):
        truth = found = said = right = false_d = 0
        for t in zone_ts:
            if t["ref_id"] is None:
                continue
            true_vids = {u["video"] for u in by_id[t["ref_id"]] if u["video"] != t["video"]}
            if not true_vids:
                continue
            seen = reid.where_seen(view, t, max_gap_s=gap)
            pred = {v for v, s in seen.items() if s["match"] and v != t["video"]}
            good = {v for v in pred if seen[v]["match"][1].get("ref_id") == t["ref_id"]}
            truth += len(true_vids); found += len(good); said += len(pred); right += len(good)
            false_d += "camD_other_road" in pred
            if name == "real_time_window" and len(true_vids) == 2 and pred == good == true_vids:
                demo.append(t)
        results[name] = {"camera_precision_%": 100 * right / max(said, 1), "camera_recall_%": 100 * found / truth,
                         "queries_wrongly_seen_in_camD_%": 100 * false_d / n}
    print(json.dumps(results, indent=1))

    mapped = [t for t in zone_ts if t["ref_id"] is not None]
    per_cam = Counter((t["ref_id"], t["video"]) for t in mapped)
    tracking = {"clean_tracklets_%": 100 * np.mean([t["purity"] >= 0.95 for t in mapped]),
                "tracklets_per_vehicle_per_camera": float(np.mean(list(per_cam.values()))),
                "unmapped_tracklets_%": 100 * (1 - len(mapped) / len(zone_ts))}
    summary = {"tracklets": {v: sum(t["video"] == v for t in view.tracklets) for v in videos},
               "vehicles_in_2plus_cameras": sum(1 for ts in by_id.values() if len({t["video"] for t in ts}) >= 2),
               "vehicles_in_all_3": sum(1 for ts in by_id.values() if len({t["video"] for t in ts}) == 3),
               "tracking": tracking, "reid": results}
    demo.sort(key=lambda t: -t["n_obs"])
    seen_ids, picks = set(), []
    for t in demo:
        if t["ref_id"] in seen_ids:
            continue
        seen_ids.add(t["ref_id"])
        picks.append({"query": t["uid"], "time": f"{t['start_t']:.1f}-{t['end_t']:.1f}", "n_obs": t["n_obs"],
                      "colour": config.COLORS[int(np.argmax(t["color_probs"]))],
                      "type": config.TYPES[int(np.argmax(t["type_probs"]))] if t["type_probs"].max() > 0 else "-"})
    summary["demo_vehicles"] = picks[:12]
    print(json.dumps(summary, indent=1))
    (config.RESULTS_DIR / "demo_eval.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
