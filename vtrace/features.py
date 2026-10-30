"""Vehicle descriptors computed for every tracklet - all from pretrained models, nothing trained by us.

* Re-ID embedding        - FastReID SBS(R50-ibn) trained on VeRi-776 (vtrace/fastreid.py), averaged over crops
* Colour / type / cues   - CLIP ViT-B/32 zero-shot ("a photo of a red car", "... with a rear spoiler", ...)
* Licence plate text     - EasyOCR, optional; only kept when confidently read
"""
import warnings

import cv2
import numpy as np
import torch
from PIL import Image

from . import config, fastreid, plate as plate_utils

warnings.filterwarnings("ignore", category=UserWarning)


def _l2(x, axis=-1):
    return x / (np.linalg.norm(x, axis=axis, keepdims=True) + 1e-12)


def _softmax(x):
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class FeatureExtractor:
    def __init__(self, device=None, use_ocr=config.ENABLE_OCR):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.reid = fastreid.load(self.device)
        self._load_clip()
        self.ocr = self._load_ocr() if use_ocr else None

    # ---------------- model loading ----------------
    def _load_clip(self):
        import open_clip
        name, pretrained = config.CLIP_MODEL
        self.clip, _, self.clip_tf = open_clip.create_model_and_transforms(name, pretrained=pretrained)
        self.clip.eval().to(self.device)
        self.tokenizer = open_clip.get_tokenizer(name)
        self.color_txt = self.encode_text([f"a photo of a {c} car" for c in config.COLORS])
        self.type_txt = self.encode_text([f"a photo of a {t}" if t in ("bus", "truck")
                                          else f"a photo of a {t} car" for t in config.TYPES])
        self.cue_txt = self.encode_text(list(config.CUES.values()))
        self.neutral_txt = self.encode_text(["a photo of a car"])[0]

    def _load_ocr(self):
        try:
            import easyocr
            return easyocr.Reader(["en"], gpu=self.device == "cuda", verbose=False)
        except Exception as e:  # OCR is optional evidence
            print(f"[V-Trace] EasyOCR unavailable ({e}); continuing without plate OCR.")
            return None

    # ---------------- encoders ----------------
    @torch.no_grad()
    def encode_text(self, texts):
        tokens = self.tokenizer(texts).to(self.device)
        return _l2(self.clip.encode_text(tokens).float().cpu().numpy())

    @torch.no_grad()
    def clip_embed(self, crops_bgr):
        imgs = [self.clip_tf(Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB))) for c in crops_bgr]
        out = self.clip.encode_image(torch.stack(imgs).to(self.device)).float().cpu().numpy()
        return _l2(out)

    def reid_embed(self, crops_bgr):
        return fastreid.embed(self.reid, crops_bgr, self.device)

    # ---------------- attribute / cue scoring (CLIP zero-shot) ----------------
    def attribute_probs(self, clip_emb):
        """Colour and type probability vectors (vocab order from config)."""
        return (_softmax(100 * self.color_txt @ clip_emb),
                _softmax(100 * self.type_txt @ clip_emb))

    def text_prob(self, clip_emb, text_emb):
        """P(prompt) vs. the neutral prompt 'a photo of a car' - a 0..1 cue score."""
        logits = 100 * np.array([text_emb @ clip_emb, self.neutral_txt @ clip_emb])
        return float(_softmax(logits)[0])

    def cue_probs(self, clip_emb):
        return np.array([self.text_prob(clip_emb, t) for t in self.cue_txt])

    def read_plate(self, crops_bgr):
        if self.ocr is None:
            return "", 0.0
        # Only the largest crops, and only when the vehicle is big enough for a legible plate (OCR is the slowest step)
        crops = sorted((c for c in crops_bgr if c.shape[1] >= config.OCR_MIN_WIDTH), key=lambda c: -c.shape[1])
        best, best_conf = "", 0.0
        for c in crops[:config.OCR_MAX_CROPS]:
            c = c[int(0.35 * c.shape[0]):]                      # plates sit in the lower part of the vehicle
            if c.shape[1] < 300:
                c = cv2.resize(c, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            for _, text, conf in self.ocr.readtext(c, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"):
                t = plate_utils.normalize(text)
                if 4 <= len(t) <= 10 and any(ch.isdigit() for ch in t) and conf > max(best_conf, 0.4):
                    best, best_conf = t, float(conf)
        return best, best_conf

    # ---------------- full descriptor ----------------
    def describe(self, crops_bgr, read_plate=True):
        clip_mean = _l2(self.clip_embed(crops_bgr).mean(0))
        color_p, type_p = self.attribute_probs(clip_mean)
        plate, plate_conf = self.read_plate(crops_bgr) if read_plate else ("", 0.0)
        return {
            "reid_emb": _l2(self.reid_embed(crops_bgr).mean(0)).astype(np.float32),
            "clip_emb": clip_mean.astype(np.float32),
            "color_probs": color_p,
            "type_probs": type_p,
            "cue_probs": self.cue_probs(clip_mean),
            "plate": plate,
            "plate_conf": plate_conf,
            "n_crops": len(crops_bgr),
        }
