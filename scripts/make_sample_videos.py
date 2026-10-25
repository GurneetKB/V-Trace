"""Create two tiny synthetic 'camera' clips for a smoke test of the full pipeline.

    python scripts/make_sample_videos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vtrace.samples import make_sample_videos

if __name__ == "__main__":
    for p in make_sample_videos():
        print("wrote", p)
