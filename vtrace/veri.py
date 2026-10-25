"""VeRi-776 benchmark loader.

Expected layout (as distributed by the dataset authors):
    data/VeRi/image_train/0001_c001_00016450_0.jpg ...
    data/VeRi/image_test/...
    data/VeRi/train_label.xml, data/VeRi/test_label.xml   (colour / type labels)

Images of the same vehicle seen by the same camera are consecutive frames of one pass,
so we group them by (vehicle, camera) into tracklets - exactly the unit the video pipeline uses.
"""
import random
import re
from collections import defaultdict

from . import config

ITEM_RE = re.compile(r"<Item\b([^>]*)/?>")
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def available():
    return (config.VERI_DIR / "image_train").exists() and (config.VERI_DIR / "image_test").exists()


def _labels(split):
    path = config.VERI_DIR / f"{split}_label.xml"
    if not path.exists():
        return {}
    text = path.read_bytes().decode("utf-8", errors="ignore")
    # colorID / typeID are 1-based and in the same order as config.COLORS / config.TYPES
    out = {}
    for item in ITEM_RE.findall(text):
        a = dict(ATTR_RE.findall(item))
        if {"imageName", "colorID", "typeID"} <= a.keys():
            out[a["imageName"]] = (int(a["colorID"]) - 1, int(a["typeID"]) - 1)
    return out


def load_tracklets(split="train", n_ids=150, k=config.CROPS_PER_TRACK, seed=0):
    folder = config.VERI_DIR / f"image_{split}"
    labels = _labels(split)
    groups = defaultdict(list)
    for p in folder.glob("*.jpg"):
        vid, cam, frame = p.stem.split("_")[:3]
        groups[(vid, cam)].append((int(frame), p))

    ids = sorted({v for v, _ in groups})
    random.Random(seed).shuffle(ids)
    keep = set(ids[:n_ids])

    tracklets = []
    for (vid, cam), imgs in sorted(groups.items()):
        if vid not in keep:
            continue
        imgs.sort()
        step = max(1, len(imgs) // k)
        chosen = [p for _, p in imgs[::step][:k]]
        lab = labels.get(chosen[0].name)
        tracklets.append({
            "uid": f"veri_{split}_{vid}_{cam}", "vehicle_id": vid, "camera": cam, "video": cam,
            "crop_paths": [str(p) for p in chosen], "n_obs": len(imgs),
            "color_label": lab[0] if lab else None, "type_label": lab[1] if lab else None,
        })
    return tracklets
