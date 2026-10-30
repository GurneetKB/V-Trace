"""Central settings for V-Trace. Edit values here rather than inside the modules."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
VIDEO_DIR = DATA_DIR / "videos"          # uploaded / demo videos (one file = one camera)
INDEX_DIR = DATA_DIR / "index"           # generated vehicle index (crops, frames, index.pkl)
# VeRi-776 benchmark (download separately, ~1 GB). Set VTRACE_VERI_DIR to keep it outside the project
# (e.g. outside OneDrive); otherwise data/VeRi is used, falling back to ~/VeRi.
VERI_DIR = Path(os.environ["VTRACE_VERI_DIR"]) if os.environ.get("VTRACE_VERI_DIR") else (
    DATA_DIR / "VeRi" if (DATA_DIR / "VeRi").exists() else Path.home() / "VeRi")
CACHE_DIR = DATA_DIR / "cache"           # cached benchmark features
MODELS_DIR = ROOT / "models"             # pretrained Re-ID weights (git-ignored, downloaded on first use)
RESULTS_DIR = ROOT / "results"
DEMO_BUNDLE = ROOT / "demo_bundle"       # pre-processed demo cameras (scripts/export_demo_bundle.py)

for _d in (VIDEO_DIR, INDEX_DIR, CACHE_DIR, MODELS_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------- Detection + tracking ----------------
YOLO_WEIGHTS = "yolo11n.pt"              # pretrained COCO detector, auto-downloaded on first run
TRACKER_CFG = "bytetrack.yaml"           # ByteTrack (ships with ultralytics)
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO ids
DET_CONF = 0.30
FRAME_STRIDE = 3                         # process every Nth frame (speed vs. accuracy)
MIN_TRACK_LEN = 4                        # drop tracks with fewer detections (noise)
MIN_CROP_SIDE = 32                       # ignore tiny boxes when choosing crops
CROPS_PER_TRACK = 4                      # representative crops stored per tracklet

# ---------------- Descriptors ----------------
CLIP_MODEL = ("ViT-B-32", "openai")
ENABLE_OCR = os.environ.get("VTRACE_OCR", "1") != "0"   # licence-plate OCR (EasyOCR); VTRACE_OCR=0 disables
OCR_MIN_WIDTH = 160                      # px; plates on smaller vehicle crops are not legible, skip OCR
OCR_MAX_CROPS = 2                        # OCR only the largest crops of each tracklet

# Vocabularies follow the VeRi-776 colour / type labels.
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

# ---------------- Cross-camera Re-ID (pretrained FastReID, VeRi-776) ----------------
MATCH_THRESHOLD = 0.40     # min cosine similarity of Re-ID embeddings for "same vehicle" (VeRi-776: scripts/eval_veri.py)
MATCH_MARGIN = 0.08        # the best sighting in a camera must beat the second best by this much (ratio test)
MAX_GAP_S = 10             # when videos are recorded at the same time: max seconds between two sightings

# Stage-1 (description search) field weights; missing fields are simply skipped
SEARCH_WEIGHTS = {"color": 0.30, "type": 0.25, "plate": 0.35, "cues": 0.10, "text": 0.10}
UNREAD_PLATE_SCORE = 0.3   # neutral score for tracklets whose plate could not be read

REID_WEIGHTS = MODELS_DIR / "veri_sbs_R50-ibn.pth"   # FastReID VeRi-776 checkpoint (downloaded on first use)
