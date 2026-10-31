"""Build the upload test pack (test_videos/): short clips to upload in the app, for the demo and for assessors.

Made from the same openly licensed recordings as the demo cameras (docs/DEMO_DATA.md), cut differently:

    set1_orchard_{west,scotts,east}.mp4   street recording 1-23 s, the three camera zones (same clock)
    set2_orchard_{west,scotts,east}.mp4   street recording 23-45 s, the three zones (other vehicles)
    set3_bukit_timah.mp4                  the other road, 1-21 s (distractor: its vehicles never appear in sets 1-2)

Their curated Singapore locations and recording starts are in vtrace/cameras.py (TEST_PACK) and fill in
automatically when the files are uploaded under these names. test_videos/README.md lists them with the results
to expect.

    python scripts/make_test_videos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from scripts.prepare_demo_clips import RAW, Y0, Y1, ZONES, frames, look

OUT = Path(__file__).resolve().parent.parent / "test_videos"
ZONE_NAMES = {"camA_west": "west", "camB_centre": "scotts", "camC_east": "east"}
SETS = {"set1": (1.0, 22.0), "set2": (23.0, 22.0)}           # (start s, duration s) in the street recording


def write(path, frame_iter, size=None):
    vw, n = None, 0
    for f, fps in frame_iter:
        if size:
            f = cv2.resize(f, size)
        vw = vw or cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, f.shape[1::-1])
        vw.write(f)
        n += 1
    vw.release()
    print(f"wrote {path.name}: {n} frames, {path.stat().st_size / 1e6:.1f} MB")


def main():
    a, b = RAW / "ljubljana_a.webm", RAW / "ljubljana_b.webm"
    if not (a.exists() and b.exists()):
        sys.exit(f"Missing the raw recordings in {RAW} - see docs/DEMO_DATA.md")
    OUT.mkdir(exist_ok=True)
    for name, (start, dur) in SETS.items():
        for cam, (x0, x1, kind) in ZONES.items():
            write(OUT / f"{name}_orchard_{ZONE_NAMES[cam]}.mp4",
                  ((look(f[Y0:Y1, x0:x1], kind), fps) for f, fps in frames(a, start, dur)))
    write(OUT / "set3_bukit_timah.mp4", frames(b, 1.0, 20.0), size=(960, 540))


if __name__ == "__main__":
    main()
