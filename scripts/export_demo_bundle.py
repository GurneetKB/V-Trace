"""Pack the processed demo cameras into demo_bundle/ (committed), so the hosted app's Quick demo loads instantly.

Streamlit Community Cloud has a small CPU and no demo videos (they are git-ignored), so processing there would take
many minutes. The bundle holds each demo tracklet's descriptors, its crops and a downscaled evidence frame, with
paths relative to the project root; VehicleIndex.import_bundle() loads it.

    python scripts/export_demo_bundle.py        # after the demo cameras are processed locally
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import joblib

from vtrace import config
from vtrace.index import VehicleIndex

CAMERAS = ["camA_west", "camB_centre", "camC_east", "camD_other_road"]


def rel(p):
    return Path(p).relative_to(config.ROOT).as_posix()


def main():
    index = VehicleIndex.load()
    missing = [c for c in CAMERAS if c not in index.videos()]
    if missing:
        sys.exit(f"Process these videos first: {missing}")
    shutil.rmtree(config.DEMO_BUNDLE, ignore_errors=True)
    out = []
    for t in (t for t in index.tracklets if t["video"] in CAMERAS):
        crops = []
        for src in t["crop_paths"]:
            dst = config.DEMO_BUNDLE / "crops" / t["video"] / Path(src).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            crops.append(rel(dst))
        frame = cv2.imread(t["frame_path"])
        if frame.shape[1] > 640:
            frame = cv2.resize(frame, None, fx=640 / frame.shape[1], fy=640 / frame.shape[1])
        dst = config.DEMO_BUNDLE / "frames" / t["video"] / Path(t["frame_path"]).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dst), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out.append(t | {"crop_paths": crops, "frame_path": rel(dst)})
    joblib.dump(out, config.DEMO_BUNDLE / "tracklets.joblib", compress=3)
    (config.DEMO_BUNDLE / "manifest.json").write_text(json.dumps(
        {c: sum(t["video"] == c for t in out) for c in CAMERAS}, indent=1))
    size = sum(f.stat().st_size for f in config.DEMO_BUNDLE.rglob("*") if f.is_file()) / 1e6
    print(f"{len(out)} tracklets -> {config.DEMO_BUNDLE} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
