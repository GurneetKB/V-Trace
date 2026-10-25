"""Create two tiny synthetic 'camera' clips for a smoke test of the full pipeline.

They pan a virtual camera over the sample images bundled with ultralytics, so the same
vehicles appear in both clips under a different zoom / brightness. Use real CCTV/traffic
clips for the actual demo - these only prove the software runs end to end.

    python scripts/make_sample_videos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
import ultralytics

from vtrace import config

ASSETS = Path(ultralytics.__file__).parent / "assets"


def pan(img, out_path, zoom, gain, frames=90, fps=15, size=(640, 480), reverse=False):
    h, w = img.shape[:2]
    cw, ch = int(w / zoom), int(h / zoom)
    xs = np.linspace(0, w - cw, frames).astype(int)
    if reverse:
        xs = xs[::-1]
    y = (h - ch) // 2
    vw = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for x in xs:
        f = cv2.resize(img[y:y + ch, x:x + cw], size)
        vw.write(cv2.convertScaleAbs(f, alpha=gain, beta=0))
    vw.release()
    print("wrote", out_path)


def main():
    img = cv2.imread(str(ASSETS / "bus.jpg"))
    if img is None:
        sys.exit(f"Sample image not found in {ASSETS}")
    pan(img, config.VIDEO_DIR / "sample_camA.mp4", zoom=1.1, gain=1.0)
    pan(img, config.VIDEO_DIR / "sample_camB.mp4", zoom=1.3, gain=0.8, reverse=True)


if __name__ == "__main__":
    main()
