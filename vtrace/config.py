"""Central settings for V-Trace. Edit values here rather than inside the modules."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
VIDEO_DIR = DATA_DIR / "videos"          # uploaded / demo videos (one file = one camera)
INDEX_DIR = DATA_DIR / "index"           # generated vehicle index (crops, frames, index.pkl)
VERI_DIR = DATA_DIR / "VeRi"             # VeRi-776 benchmark (download separately)
CACHE_DIR = DATA_DIR / "cache"           # cached benchmark features
MODELS_DIR = ROOT / "models"             # trained Random Forest + attribute probes
RESULTS_DIR = ROOT / "results"           # evaluation metrics and plots

for _d in (VIDEO_DIR, INDEX_DIR, CACHE_DIR, MODELS_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------- Detection + tracking ----------------
YOLO_WEIGHTS = "yolo11n.pt"              # pretrained COCO detector, auto-downloaded on first run
TRACKER_CFG = "bytetrack.yaml"           # ByteTrack (ships with ultralytics)
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO ids
DET_CONF = 0.30
FRAME_STRIDE = 2                         # process every Nth frame (speed vs. accuracy)
MIN_TRACK_LEN = 4                        # drop tracks with fewer detections (noise)
MIN_CROP_SIDE = 32                       # ignore tiny boxes when choosing crops
CROPS_PER_TRACK = 4                      # representative crops stored per tracklet

# ---------------- Descriptors ----------------
CLIP_MODEL = ("ViT-B-32", "openai")
ENABLE_OCR = os.environ.get("VTRACE_OCR", "1") != "0"   # licence-plate OCR (EasyOCR); VTRACE_OCR=0 disables

# Vocabularies follow the VeRi-776 labels so the benchmark can evaluate them.
COLORS = ["yellow", "orange", "green", "gray", "red", "blue", "white", "golden", "brown", "black"]
TYPES = ["sedan", "suv", "van", "hatchback", "mpv", "pickup", "bus", "truck", "estate"]
# Controlled vocabulary of optional distinctive cues (scored with CLIP text-image similarity)
CUES = {
    "roof rack": "a photo of a car with a roof rack",
    "rear spoiler": "a photo of a car with a rear spoiler",
    "dent / body damage": "a photo of a car with a dent or damaged body panel",
    "sticker / decal": "a photo of a car with a large sticker or decal",
    "cargo on roof": "a photo of a vehicle carrying cargo on its roof",
}

# ---------------- Matching / fusion ----------------
PAIR_FEATURES = [
    "app_cos",        # CNN (ResNet-50) appearance embedding cosine similarity
    "clip_cos",       # CLIP image embedding cosine similarity
    "color_hist",     # HSV colour-histogram intersection
    "color_agree",    # probability both tracklets have the same colour
    "type_agree",     # probability both tracklets have the same type
    "plate_sim",      # plate string similarity (0 if either plate unreadable)
    "plate_avail",    # 1 if both plates were read
    "cue_sim",        # agreement of distinctive-cue scores
    "track_quality",  # min #crops of the two tracklets / CROPS_PER_TRACK
    "track_consist",  # min intra-tracklet appearance consistency
]

# Transparent weighted-fusion baseline (plate weight only used when both plates read)
FUSION_WEIGHTS = {
    "app_cos": 0.35, "clip_cos": 0.20, "color_hist": 0.10,
    "color_agree": 0.10, "type_agree": 0.10, "cue_sim": 0.05, "plate_sim": 0.30,
}

# Stage-1 (description search) field weights; missing fields are simply skipped
SEARCH_WEIGHTS = {"color": 0.30, "type": 0.25, "plate": 0.35, "cues": 0.10, "text": 0.10}
UNREAD_PLATE_SCORE = 0.3   # neutral score for tracklets whose plate could not be read

RF_PATH = MODELS_DIR / "rf_matcher.joblib"
ATTR_PROBE_PATH = MODELS_DIR / "attr_probe.joblib"
