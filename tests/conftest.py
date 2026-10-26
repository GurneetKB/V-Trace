"""Synthetic tracklets so the matching logic can be tested without vision models."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vtrace import config  # noqa: E402


def _unit(v):
    return (v / np.linalg.norm(v)).astype(np.float32)


def _onehot(n, i, conf=0.9):
    p = np.full(n, (1 - conf) / (n - 1))
    p[i] = conf
    return p


@pytest.fixture
def make_tracklet():
    rng = np.random.default_rng(0)
    bases = {}

    def make(uid, video, vehicle=None, color="white", vtype="suv", plate="", noise=0.05):
        """Tracklets sharing `vehicle` get near-identical embeddings."""
        key = vehicle or uid
        if key not in bases:
            bases[key] = (rng.normal(size=2048), rng.normal(size=512), rng.random(256))
        app, clip, hist = bases[key]
        hist = hist + noise * rng.random(256)
        return {
            "uid": uid, "video": video, "camera": video, "track_id": 1, "n_obs": 20,
            "app_emb": _unit(app + noise * rng.normal(size=2048)),
            "clip_emb": _unit(clip + noise * rng.normal(size=512)),
            "color_probs": _onehot(len(config.COLORS), config.COLORS.index(color)),
            "type_probs": _onehot(len(config.TYPES), config.TYPES.index(vtype)),
            "cue_probs": np.full(len(config.CUES), 0.3),
            "hsv_hist": (hist / hist.sum()).astype(np.float32),
            "plate": plate, "plate_conf": 0.9 if plate else 0.0,
            "n_crops": config.CROPS_PER_TRACK, "consistency": 0.95,
        }

    return make
