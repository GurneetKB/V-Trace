"""Build the demo 'cameras' from openly licensed Wikimedia Commons traffic recordings.

Sources (CC BY 3.0, "Sounds of Changes" project, Wikimedia Commons; see docs/DEMO_DATA.md):
    data/videos/raw/ljubljana_a.webm  <- File:Road traffic in Ljubljana.webm
    data/videos/raw/ljubljana_b.webm  <- File:Road traffic in Ljubljana – soundscape 1.webm

Clip A is a wide 1080p shot of a road that vehicles cross from one side to the other in 5-10 s. It is cut
into three non-overlapping zones along the road, with gaps between them, and each zone gets its own
exposure / colour cast / sharpness, like three different cameras placed along the street:

    camA_west.mp4    left zone   (x    0-560)  - reference camera
    camB_centre.mp4  middle zone (x  680-1240) - darker, colder, slightly soft
    camC_east.mp4    right zone  (x 1360-1920) - warmer, higher contrast

A car driving left-to-right is therefore seen in camA, then camB, then camC (right-to-left: C, B, A), with
real changes in scale and viewpoint along the way, which is what the "trace its path" demo needs.

    camD_other_road.mp4  clip B, a different road: distractor camera (its vehicles never appear in A-C)

    python scripts/prepare_demo_clips.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from vtrace import config

RAW = config.VIDEO_DIR / "raw"
Y0, Y1 = 380, 940                        # road band of clip A (1080p)
ZONES = {                                # name: (x0, x1, look)
    "camA_west": (0, 560, "reference"),
    "camB_centre": (680, 1240, "cold"),
    "camC_east": (1360, 1920, "warm"),
}


def frames(path, start_s, dur_s):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    i = 0
    while True:
        ok, f = cap.read()
        if not ok or i >= (start_s + dur_s) * fps:
            break
        if i >= start_s * fps:
            yield f, fps
        i += 1
    cap.release()


def look(f, kind):
    """Give each zone its own camera character (exposure, white balance, sharpness)."""
    if kind == "cold":
        f = cv2.GaussianBlur(cv2.convertScaleAbs(f, alpha=0.85, beta=-10), (3, 3), 0)
        b, g, r = cv2.split(f.astype(np.int16))
        return cv2.merge([np.clip(b + 14, 0, 255), g, np.clip(r - 10, 0, 255)]).astype(np.uint8)
    if kind == "warm":
        f = cv2.convertScaleAbs(f, alpha=1.12, beta=-12)
        b, g, r = cv2.split(f.astype(np.int16))
        return cv2.merge([np.clip(b - 12, 0, 255), g, np.clip(r + 12, 0, 255)]).astype(np.uint8)
    return f


def main():
    a, b = RAW / "ljubljana_a.webm", RAW / "ljubljana_b.webm"
    missing = [p.name for p in (a, b) if not p.exists()]
    if missing:
        sys.exit(f"Missing {missing} in {RAW} - see docs/DEMO_DATA.md for the download links.")

    writers, n = {}, 0
    for f, fps in frames(a, 1.0, 45):                          # skip the black fade-in; whole clip
        for name, (x0, x1, kind) in ZONES.items():
            crop = look(f[Y0:Y1, x0:x1], kind)
            if name not in writers:
                writers[name] = cv2.VideoWriter(str(config.VIDEO_DIR / f"{name}.mp4"),
                                                cv2.VideoWriter_fourcc(*"mp4v"), fps, crop.shape[1::-1])
            writers[name].write(crop)
        n += 1
    for name, w in writers.items():
        w.release()
        print(f"wrote {name}.mp4: {n} frames")

    vw, n = None, 0
    for f, fps in frames(b, 1.0, 30):
        f = cv2.resize(f, (1280, 720))
        vw = vw or cv2.VideoWriter(str(config.VIDEO_DIR / "camD_other_road.mp4"),
                                   cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
        vw.write(f)
        n += 1
    vw.release()
    print(f"wrote camD_other_road.mp4: {n} frames")


if __name__ == "__main__":
    main()
