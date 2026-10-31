"""Cross-camera re-identification with the pretrained FastReID VeRi-776 model.

Each sighting (tracklet) has one Re-ID embedding (mean of its crops' FastReID embeddings, L2-normalised); the
similarity of two sightings is the cosine of their embeddings. For the selected vehicle, every other camera's
sightings are ranked by similarity and the best one is reported as the same vehicle when
  * its similarity is at least config.MATCH_THRESHOLD, and
  * it beats that camera's second-best sighting by config.MATCH_MARGIN (Lowe's ratio test: when two vehicles look
    equally similar the answer is ambiguous, so it is left to the user), and
  * optionally, it is within max_gap_s seconds of the selected one in real-world time (camera recording start +
    position in the video, vtrace/cameras.py); cameras whose recording start is unknown are not time-limited.
"""
from . import config


def similarity(a, b):
    return float(a["reid_emb"] @ b["reid_emb"])


def gap(a, b):
    """Real-world seconds between two sightings' time spans (0 if they overlap or a recording start is unknown)."""
    if a.get("real_start") is None or b.get("real_start") is None:
        return 0.0
    return max(0.0, (a["real_start"] - b["real_end"]).total_seconds(), (b["real_start"] - a["real_end"]).total_seconds())


def rank(index, query, videos=None, max_gap_s=None):
    """Sightings in other cameras, most similar first: [(score, tracklet)]."""
    hits = [(similarity(query, t), t) for t in index.tracklets
            if t["video"] != query["video"] and (videos is None or t["video"] in videos)
            and (max_gap_s is None or gap(query, t) <= max_gap_s)]
    return sorted(hits, key=lambda h: -h[0])


def where_seen(index, query, threshold=None, margin=None, max_gap_s=None):
    """Where the selected vehicle was seen: {camera: {"match": (score, t) or None, "candidates": [(score, t)]}}.

    Every camera in the index is listed. The selected camera's match is the query itself. `candidates` are the three
    most similar sightings in that camera, shown so the user can check a result or decide when there is no match.
    """
    threshold = config.MATCH_THRESHOLD if threshold is None else threshold
    margin = config.MATCH_MARGIN if margin is None else margin
    out = {}
    for video in index.videos():
        if video == query["video"]:
            out[video] = {"match": (1.0, query), "candidates": []}
            continue
        hits = rank(index, query, {video}, max_gap_s)
        ok = hits and hits[0][0] >= threshold and (len(hits) == 1 or hits[0][0] - hits[1][0] >= margin)
        out[video] = {"match": hits[0] if ok else None, "candidates": hits[:3]}
    return out


def route(seen):
    """The matched sightings in real-world time order (video time when a recording start is unknown)."""
    return sorted((s["match"][1] for s in seen.values() if s["match"]),
                  key=lambda t: (t.get("real_start") is None, t.get("real_start") or 0, t["start_t"]))
