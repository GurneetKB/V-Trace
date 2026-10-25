"""Video ingestion -> vehicle detection (YOLO) -> within-video tracking (ByteTrack) -> tracklets.

A tracklet is the set of detections of one vehicle while it is visible in one video/camera.
For each tracklet we keep a few good, time-spread crops and one annotated evidence frame.
"""
from collections import Counter
from pathlib import Path

import cv2

from . import config

MAX_CANDIDATES = 16  # crops kept in memory per track before final selection


def _quality(box, conf, w, h):
    x1, y1, x2, y2 = box
    q = (x2 - x1) * (y2 - y1) * conf
    if x1 <= 2 or y1 <= 2 or x2 >= w - 2 or y2 >= h - 2:  # truncated at the frame border
        q *= 0.5
    return q


def _select_crops(cands, k, min_gap):
    """Pick k high-quality crops that are spread out in time."""
    order = sorted(range(len(cands)), key=lambda i: -cands[i][0])
    chosen = []
    for i in order:
        if len(chosen) < k and all(abs(cands[i][1] - cands[j][1]) >= min_gap for j in chosen):
            chosen.append(i)
    for i in order:  # top up if the track was short
        if len(chosen) < k and i not in chosen:
            chosen.append(i)
    return [cands[i] for i in sorted(chosen, key=lambda i: cands[i][1])]


def fmt_time(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def process_video(video_path, camera=None, progress=None):
    """Detect and track vehicles in one video.

    Returns (tracklets, crops) where tracklets is a list of metadata dicts and
    crops maps tracklet uid -> list of BGR crop arrays (for descriptor extraction).
    """
    from ultralytics import YOLO

    video_path = Path(video_path)
    name = video_path.stem
    camera = camera or name
    model = YOLO(config.YOLO_WEIGHTS)  # fresh model => fresh tracker state per video

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    tracks = {}
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % config.FRAME_STRIDE == 0:
            h, w = frame.shape[:2]
            res = model.track(frame, persist=True, tracker=config.TRACKER_CFG, conf=config.DET_CONF,
                              classes=list(config.VEHICLE_CLASSES), verbose=False)[0]
            if res.boxes is not None and res.boxes.id is not None:
                boxes = res.boxes.xyxy.cpu().numpy()
                ids = res.boxes.id.int().cpu().tolist()
                clss = res.boxes.cls.int().cpu().tolist()
                confs = res.boxes.conf.cpu().tolist()
                for box, tid, cls, conf in zip(boxes, ids, clss, confs):
                    tr = tracks.setdefault(tid, {"frames": [], "cls": Counter(), "cands": [], "best": None})
                    tr["frames"].append(idx)
                    tr["cls"][config.VEHICLE_CLASSES.get(cls, "car")] += 1
                    x1, y1, x2, y2 = [int(v) for v in box]
                    x1, y1 = max(0, x1), max(0, y1)
                    if min(x2 - x1, y2 - y1) < config.MIN_CROP_SIDE:
                        continue
                    q = _quality((x1, y1, x2, y2), conf, w, h)
                    tr["cands"].append((q, idx, frame[y1:y2, x1:x2].copy()))
                    if len(tr["cands"]) > MAX_CANDIDATES:
                        worst = min(range(len(tr["cands"])), key=lambda i: tr["cands"][i][0])
                        tr["cands"].pop(worst)
                    if tr["best"] is None or q > tr["best"][0]:
                        tr["best"] = (q, idx, frame.copy(), (x1, y1, x2, y2))
            if progress:
                progress(min(idx / total, 1.0))
        idx += 1
    cap.release()

    crop_dir = config.INDEX_DIR / "crops" / name
    frame_dir = config.INDEX_DIR / "frames" / name
    crop_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    tracklets, crops = [], {}
    for tid, tr in tracks.items():
        if len(tr["frames"]) < config.MIN_TRACK_LEN or not tr["cands"]:
            continue
        uid = f"{name}#{tid}"
        chosen = _select_crops(tr["cands"], config.CROPS_PER_TRACK, min_gap=int(fps // 2))
        crop_paths = []
        for k, (_, _, crop) in enumerate(chosen):
            p = crop_dir / f"{tid}_{k}.jpg"
            cv2.imwrite(str(p), crop)
            crop_paths.append(str(p))

        _, best_idx, best_frame, (x1, y1, x2, y2) = tr["best"]
        cv2.rectangle(best_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(best_frame, f"{camera} | track {tid} | {fmt_time(best_idx / fps)}", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        scale = 960 / best_frame.shape[1]
        if scale < 1:
            best_frame = cv2.resize(best_frame, None, fx=scale, fy=scale)
        frame_path = frame_dir / f"{tid}.jpg"
        cv2.imwrite(str(frame_path), best_frame)

        tracklets.append({
            "uid": uid, "video": name, "camera": camera, "track_id": tid,
            "yolo_class": tr["cls"].most_common(1)[0][0],
            "n_obs": len(tr["frames"]),
            "start_frame": tr["frames"][0], "end_frame": tr["frames"][-1],
            "start_t": tr["frames"][0] / fps, "end_t": tr["frames"][-1] / fps,
            "best_t": best_idx / fps, "fps": fps,
            "crop_paths": crop_paths, "frame_path": str(frame_path),
        })
        crops[uid] = [c[2] for c in chosen]
    return tracklets, crops
