"""Two tiny synthetic 'camera' clips for a smoke test / demo without real footage.

They pan a virtual camera over a sample image bundled with ultralytics, so the same
vehicle appears in both clips under a different zoom / brightness. Use real CCTV or
traffic clips for the actual demo.
"""
from pathlib import Path

import cv2
import numpy as np

from . import config


def _pan(img, out_path, zoom, gain, frames=90, fps=15, size=(640, 480), reverse=False):
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
    return out_path


def make_sample_videos():
    import ultralytics
    img = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    if img is None:
        raise FileNotFoundError("ultralytics sample image bus.jpg not found")
    return [_pan(img, config.VIDEO_DIR / "sample_camA.mp4", zoom=1.1, gain=1.0),
            _pan(img, config.VIDEO_DIR / "sample_camB.mp4", zoom=1.3, gain=0.8, reverse=True)]
