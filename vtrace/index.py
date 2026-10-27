"""Searchable vehicle index: one entry per tracklet with all of its descriptors."""
import shutil

import joblib
import numpy as np

from . import config
from .som import VehicleSOM
from .video import process_video

INDEX_FILE = config.INDEX_DIR / "index.pkl"


class VehicleIndex:
    def __init__(self, tracklets=None):
        self.tracklets = tracklets or []
        self.som = None

    # ---------- persistence ----------
    @classmethod
    def load(cls, path=INDEX_FILE):
        if path.exists():
            return joblib.load(path)
        return cls()

    def save(self, path=INDEX_FILE):
        joblib.dump(self, path)

    # ---------- building ----------
    def videos(self):
        return sorted({t["video"] for t in self.tracklets})

    def remove_video(self, name):
        self.tracklets = [t for t in self.tracklets if t["video"] != name]
        for sub in ("crops", "frames"):
            shutil.rmtree(config.INDEX_DIR / sub / name, ignore_errors=True)

    def add_video(self, video_path, extractor, camera=None, progress=None, stride=None, read_plate=True):
        """Detect + track + describe every vehicle in a video and add it to the index."""
        from pathlib import Path
        name = Path(video_path).stem
        self.remove_video(name)
        track_prog = (lambda f: progress(0.8 * f)) if progress else None
        tracklets, crops = process_video(video_path, camera, track_prog, stride)
        for i, t in enumerate(tracklets):
            t.update(extractor.describe(crops[t["uid"]], read_plate=read_plate))
            if t["yolo_class"] == "motorcycle":           # outside the CLIP car-type vocabulary
                t["type_probs"] = np.zeros(len(config.TYPES))
            if progress:
                progress(0.8 + 0.2 * (i + 1) / max(len(tracklets), 1))
        self.tracklets.extend(tracklets)
        return len(tracklets)

    def fit_som(self):
        if len(self.tracklets) >= 4:
            self.som = VehicleSOM().fit(self.matrix("app_emb"))
        else:
            self.som = None
        return self.som

    # ---------- access ----------
    def get(self, uid):
        return next(t for t in self.tracklets if t["uid"] == uid)

    def matrix(self, key, tracklets=None):
        return np.stack([t[key] for t in (tracklets or self.tracklets)])

    def __len__(self):
        return len(self.tracklets)
