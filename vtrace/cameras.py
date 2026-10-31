"""Real-world camera details: where each camera is and when its video started recording.

A sighting's real-world time = the camera's recording start + the sighting's position in the video. Cameras can be
seconds, minutes or hours apart; the Re-ID time window compares these real-world times (vtrace/reid.py).

The demo and test videos carry no location or clock metadata, so the details below are CURATED: the footage is
placed on Singapore roads. camA-camC are three zones of one recording (same clock, about 80 m apart along Orchard
Road, `docs/DEMO_DATA.md`) and camD is a different road recorded a few minutes later. The upload test pack
(`test_videos/`, built by scripts/make_test_videos.py) gets its details the same way, so they fill in automatically
when those files are uploaded. Other uploads get their details from the user.
"""
from datetime import datetime, timedelta

_ORCHARD = {"west": ("Orchard Road, west of Scotts Road · Singapore", 1.30440, 103.83140),
            "scotts": ("Orchard Road at the Scotts Road junction · Singapore", 1.30462, 103.83215),
            "east": ("Orchard Road, east of Scotts Road · Singapore", 1.30484, 103.83290)}
_BUKIT_TIMAH = ("Bukit Timah Road near Newton Circus · Singapore", 1.31300, 103.83800)


def _cam(place, start):
    loc, lat, lon = place
    return {"location": loc, "lat": lat, "lon": lon, "start": start}


DEMO = {
    "camA_west": _cam(_ORCHARD["west"], "2026-10-28T08:15:00"),
    "camB_centre": _cam(_ORCHARD["scotts"], "2026-10-28T08:15:00"),
    "camC_east": _cam(_ORCHARD["east"], "2026-10-28T08:15:00"),
    "camD_other_road": _cam(_BUKIT_TIMAH, "2026-10-28T08:17:30"),
}
# Upload test pack: set 1 = 1-23 s of the street recording, set 2 = 23-45 s (other vehicles), set 3 = another road
TEST_PACK = {
    **{f"set1_orchard_{z}": _cam(_ORCHARD[z], "2026-10-30T17:45:01") for z in _ORCHARD},
    **{f"set2_orchard_{z}": _cam(_ORCHARD[z], "2026-10-30T17:45:23") for z in _ORCHARD},
    "set3_bukit_timah": _cam(_BUKIT_TIMAH, "2026-10-30T17:48:00"),
}
FIELDS = ("location", "lat", "lon", "start")


def info(cameras, video):
    """Details for one camera: user-set (`cameras`, saved with the index) > curated demo / test-pack details > unknown."""
    base = {"location": "", "lat": None, "lon": None, "start": None}
    curated = DEMO.get(video) or TEST_PACK.get(video, {})
    return base | curated | {k: v for k, v in cameras.get(video, {}).items() if k in FIELDS}


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
