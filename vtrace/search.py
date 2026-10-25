"""Stage 1 - description-to-vehicle retrieval.

The user describes the target with whatever they know (colour, type, full/partial plate,
distinctive cues, free text). Every tracklet gets a score per provided field; the final
score is the weighted mean over the fields that were actually provided, so missing
information never blocks retrieval.
"""
import numpy as np

from . import config, plate as plate_utils


def field_scores(t, color=None, vtype=None, plate=None, cues=(), text_emb=None, extractor=None):
    s = {}
    if color:
        p = t["color_probs"]
        s["color"] = float(p[config.COLORS.index(color)] / (p.max() + 1e-12))
    if vtype:
        p = t["type_probs"]
        s["type"] = float(p[config.TYPES.index(vtype)] / (p.max() + 1e-12)) if p.max() > 0 else 0.0
    if plate:
        s["plate"] = (plate_utils.query_similarity(plate, t["plate"]) if t.get("plate")
                      else config.UNREAD_PLATE_SCORE)
    if cues:
        names = list(config.CUES)
        s["cues"] = float(np.mean([t["cue_probs"][names.index(c)] for c in cues]))
    if text_emb is not None and extractor is not None:
        s["text"] = extractor.text_prob(t["clip_emb"], text_emb)
    return s


def describe_search(index, color=None, vtype=None, plate=None, cues=(), free_text=None,
                    extractor=None, videos=None, top_k=20):
    """Return a ranked list of (score, tracklet, per-field evidence)."""
    text_emb = None
    if free_text and extractor is not None:
        text_emb = extractor.encode_text([f"a photo of a {free_text}"])[0]
    results = []
    for t in index.tracklets:
        if videos and t["video"] not in videos:
            continue
        s = field_scores(t, color, vtype, plate, cues, text_emb, extractor)
        if s:
            w = {k: config.SEARCH_WEIGHTS[k] for k in s}
            score = sum(w[k] * s[k] for k in s) / sum(w.values())
        else:  # nothing described: fall back to track quality so the user can browse
            score = min(t["n_obs"] / 50, 1.0)
        results.append((score, t, s))
    results.sort(key=lambda r: -r[0])
    return results[:top_k]
