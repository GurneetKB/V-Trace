"""Real-world camera details: where each camera is and when its video started recording.

A sighting's real-world time = the camera's recording start + the sighting's position in the video. Cameras can be
seconds, minutes or hours apart; the Re-ID time window compares these real-world times (vtrace/reid.py).

The demo videos carry no location or clock metadata, so the details below are CURATED for the demo: camA-camC are
three zones of one recording (same clock, a few tens of metres apart along one street, `docs/DEMO_DATA.md`) and
camD is a different road recorded a few minutes later. Uploaded videos get their details from the user.
"""
from datetime import datetime, timedelta

DEMO = {
    "camA_west": {"location": "Slovenska cesta, west of the crossing · Ljubljana", "lat": 46.05010, "lon": 14.50270,
                  "start": "2026-10-28T08:15:00"},
    "camB_centre": {"location": "Slovenska cesta, at the crossing · Ljubljana", "lat": 46.05032, "lon": 14.50306,
                    "start": "2026-10-28T08:15:00"},
    "camC_east": {"location": "Slovenska cesta, east of the crossing · Ljubljana", "lat": 46.05054, "lon": 14.50342,
                  "start": "2026-10-28T08:15:00"},
    "camD_other_road": {"location": "Celovška cesta · Ljubljana", "lat": 46.06420, "lon": 14.49260,
                        "start": "2026-10-28T08:17:30"},
}
FIELDS = ("location", "lat", "lon", "start")


def info(cameras, video):
    """Details for one camera: user-set (`cameras`, saved with the index) > curated demo details > unknown."""
    base = {"location": "", "lat": None, "lon": None, "start": None}
    return base | DEMO.get(video, {}) | {k: v for k, v in cameras.get(video, {}).items() if k in FIELDS}


def start_time(cam):
    try:
        return datetime.fromisoformat(cam["start"]) if cam.get("start") else None
    except ValueError:
        return None


def apply(tracklets, cameras):
    """Attach each sighting's camera location and real-world start/end time (None when the start is unknown)."""
    for t in tracklets:
        cam = info(cameras, t["video"])
        t0 = start_time(cam)
        t["location"], t["lat"], t["lon"] = cam["location"], cam["lat"], cam["lon"]
        t["real_start"] = t0 + timedelta(seconds=t["start_t"]) if t0 else None
        t["real_end"] = t0 + timedelta(seconds=t["end_t"]) if t0 else None
        t["real_best"] = t0 + timedelta(seconds=t.get("best_t", t["start_t"])) if t0 else None


def fmt(dt, date=True):
    """'Tue 28 Oct 2026 · 08:15:42.0' (or the time only)."""
    if dt is None:
        return "time unknown"
    clock = dt.strftime("%H:%M:%S") + f".{dt.microsecond // 100000}"
    return f"{dt.strftime('%a %d %b %Y')} · {clock}" if date else clock


def fmt_gap(seconds):
    """A time difference in words: '1.2 s', '2 min 30 s', '3 h 05 min'."""
    s = abs(seconds)
    if s < 60:
        return f"{s:.1f} s"
    if s < 3600:
        return f"{int(s // 60)} min {int(s % 60):02d} s"
    return f"{int(s // 3600)} h {int(s % 3600 // 60):02d} min"
