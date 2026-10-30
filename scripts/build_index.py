"""Build the vehicle index from videos without the UI.

    python scripts/build_index.py                       # every video in data/videos
    python scripts/build_index.py path/to/camA.mp4 path/to/camB.mp4
    python scripts/build_index.py --stride 5 --no-ocr        # faster
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vtrace import config
from vtrace.features import FeatureExtractor
from vtrace.index import VehicleIndex

VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--stride", type=int, default=config.FRAME_STRIDE, help="process every Nth frame")
    ap.add_argument("--no-ocr", action="store_true", help="skip licence-plate OCR (much faster)")
    args = ap.parse_args()
    videos = [Path(p) for p in args.videos] or sorted(p for p in config.VIDEO_DIR.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not videos:
        sys.exit(f"No videos given and none found in {config.VIDEO_DIR}")
    fe = FeatureExtractor(use_ocr=not args.no_ocr)
    index = VehicleIndex.load()
    for v in videos:
        print(f"Processing {v.name} ...")
        n = index.add_video(v, fe, progress=lambda f: print(f"\r  {100 * f:5.1f}%", end=""),
                            stride=args.stride, read_plate=not args.no_ocr)
        print(f"\n  {n} vehicle tracklets")
    index.save()
    print(f"Index: {len(index)} tracklets from {len(index.videos())} videos -> {config.INDEX_DIR}")
    for t in index.tracklets:
        print(f"  {t['uid']:30s} {t['yolo_class']:10s} {config.COLORS[t['color_probs'].argmax()]:7s} "
              f"{config.TYPES[t['type_probs'].argmax()] if t['type_probs'].max() > 0 else '-':10s} "
              f"plate={t['plate'] or '-':10s} t={t['start_t']:.1f}-{t['end_t']:.1f}s")


if __name__ == "__main__":
    main()
