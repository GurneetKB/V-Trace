"""Build the demo 'cameras' from openly licensed Wikimedia Commons traffic recordings.

Sources (CC BY 3.0, "Sounds of Changes" project, Wikimedia Commons; see docs/DEMO_DATA.md):
    data/videos/raw/ljubljana_a.webm  <- File:Road traffic in Ljubljana.webm
    data/videos/raw/ljubljana_b.webm  <- File:Road traffic in Ljubljana – soundscape 1.webm

Output (data/videos/):
    camA_main_road.mp4     real clip A (720p)
    camB_second_view.mp4   SIMULATED second camera on the same road: clip A re-framed (crop + zoom),
                           darker, colder colour balance and a 1.5 s clock offset. The same vehicles
                           appear in A and B, which gives the cross-camera Re-ID demo a true match.
    camC_other_road.mp4    real clip B, a different road (distractor camera)

    python scripts/prepare_demo_clips.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from vtrace import config

RAW = config.VIDEO_DIR / "raw"
SIZE = (1280, 720)


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


def write(out, gen, transform=lambda f: f):
    vw = None
    n = 0
    for f, fps in gen:
        f = cv2.resize(transform(f), SIZE)
        if vw is None:
            vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, SIZE)
        vw.write(f)
        n += 1
    vw.release()
    print(f"wrote {out.name}: {n} frames")


def second_view(f):
    """Re-frame like a different camera: right-hand crop, zoom, darker and colder."""
    h, w = f.shape[:2]
    crop = f[int(0.12 * h):int(0.92 * h), int(0.22 * w):w]
    crop = cv2.convertScaleAbs(crop, alpha=0.82, beta=-8)
    b, g, r = cv2.split(crop.astype(np.int16))
    return cv2.merge([np.clip(b + 12, 0, 255), g, np.clip(r - 10, 0, 255)]).astype(np.uint8)


def main():
    a, b = RAW / "ljubljana_a.webm", RAW / "ljubljana_b.webm"
    missing = [p.name for p in (a, b) if not p.exists()]
    if missing:
        sys.exit(f"Missing {missing} in {RAW} - see docs/DEMO_DATA.md for the download links.")
    write(config.VIDEO_DIR / "camA_main_road.mp4", frames(a, 1.0, 30))          # skip the black fade-in
    write(config.VIDEO_DIR / "camB_second_view.mp4", frames(a, 2.5, 30), second_view)
    write(config.VIDEO_DIR / "camC_other_road.mp4", frames(b, 1.0, 30))


if __name__ == "__main__":
    main()
