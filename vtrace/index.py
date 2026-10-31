"""Searchable vehicle index: one entry per tracklet with all of its descriptors."""
import json
import shutil
from pathlib import Path

import joblib
import numpy as np

from . import cameras as cams, config
from .video import process_video

INDEX_FILE = config.INDEX_DIR / "index.pkl"


class VehicleIndex:
    def __init__(self, tracklets=None):
        self.tracklets = tracklets or []
        self.processed = {}  # video name -> signature of the file + settings it was processed with
        self.cameras = {}    # video name -> real-world details set by the user (vtrace/cameras.py)

    # ---------- persistence ----------
    @classmethod
    def load(cls, path=INDEX_FILE):
        if path.exists():
            index = joblib.load(path)
            index.__dict__.setdefault("processed", {})  # indexes saved before caching existed
            index.__dict__.setdefault("cameras", {})
            return index
        return cls()

    def save(self, path=INDEX_FILE):
        joblib.dump(self, path)

    # ---------- building ----------
    def videos(self):
        return sorted({t["video"] for t in self.tracklets})

    def remove_video(self, name):
        self.tracklets = [t for t in self.tracklets if t["video"] != name]
        self.processed.pop(name, None)
        for sub in ("crops", "frames"):
            shutil.rmtree(config.INDEX_DIR / sub / name, ignore_errors=True)

    @staticmethod
    def signature(video_path, stride, read_plate):
        """Identifies a video file + processing settings, so unchanged videos are not reprocessed."""
        st = Path(video_path).stat()
        return (st.st_size, int(st.st_mtime), stride or config.FRAME_STRIDE, bool(read_plate))

    @staticmethod
    def bundled_videos():
        """Demo cameras available pre-processed in demo_bundle/ (empty if there is no bundle)."""
        manifest = config.DEMO_BUNDLE / "manifest.json"
        return set(json.loads(manifest.read_text())) if manifest.exists() else set()

    def import_bundle(self, names):
        """Add pre-processed demo cameras from demo_bundle/ (used where the videos are not available or would be
        slow to process, e.g. on Streamlit Community Cloud). Bundle paths are relative to the project root."""
        data = joblib.load(config.DEMO_BUNDLE / "tracklets.joblib")
        for name in names:
            self.tracklets = [t for t in self.tracklets if t["video"] != name]
            self.tracklets += [t | {"crop_paths": [str(config.ROOT / p) for p in t["crop_paths"]],
                                    "frame_path": str(config.ROOT / t["frame_path"])}
                               for t in data if t["video"] == name]
            self.processed[name] = "demo bundle"

    def is_processed(self, video_path, stride=None, read_plate=True):
        name, sig = Path(video_path).stem, self.signature(video_path, stride, read_plate)
        return name in self.processed and self.processed[name] == sig

    def add_video(self, video_path, extractor, camera=None, progress=None, stride=None, read_plate=True):
        """Detect + track + describe every vehicle in a video and add it to the index."""
        name = Path(video_path).stem
        self.remove_video(name)
        track_prog = (lambda f: progress(0.8 * f)) if progress else None
        tracklets, crops = process_video(video_path, camera, track_prog, stride)
        self.processed[name] = self.signature(video_path, stride, read_plate)
        for i, t in enumerate(tracklets):
            t.update(extractor.describe(crops[t["uid"]], read_plate=read_plate))
            if t["yolo_class"] == "motorcycle":           # outside the CLIP car-type vocabulary
                t["type_probs"] = np.zeros(len(config.TYPES))
            if progress:
                progress(0.8 + 0.2 * (i + 1) / max(len(tracklets), 1))
        self.tracklets.extend(tracklets)
        return len(tracklets)

    def subset(self, videos):
        """A view holding only the given videos (what the user is currently working with), with each sighting's
        camera location and real-world time attached."""
        view = VehicleIndex([dict(t) for t in self.tracklets if t["video"] in set(videos)])
        view.cameras = self.cameras
        cams.apply(view.tracklets, self.cameras)
        return view

    def camera(self, video):
        return cams.info(self.cameras, video)

    def set_camera(self, video, **details):
        self.cameras[video] = self.camera(video) | details

    # ---------- access ----------
    def get(self, uid):
        return next(t for t in self.tracklets if t["uid"] == uid)

    def matrix(self, key, tracklets=None):
        return np.stack([t[key] for t in (tracklets or self.tracklets)])

    def __len__(self):
        return len(self.tracklets)
