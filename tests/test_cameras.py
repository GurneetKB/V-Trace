from datetime import datetime

from vtrace import cameras
from vtrace.index import VehicleIndex


def test_real_world_time_is_recording_start_plus_video_position():
    t = {"video": "cam1", "start_t": 40.8, "end_t": 42.2, "best_t": 41.5}
    cameras.apply([t], {"cam1": {"location": "Orchard Rd", "start": "2026-10-28T08:15:00"}})
    assert t["location"] == "Orchard Rd"
    assert t["real_start"] == datetime(2026, 10, 28, 8, 15, 40, 800000)
    assert cameras.fmt(t["real_start"]) == "Wed 28 Oct 2026 · 08:15:40.8"


def test_unknown_start_gives_no_real_time():
    t = {"video": "upload", "start_t": 1.0, "end_t": 2.0}
    cameras.apply([t], {})
    assert t["real_start"] is None and cameras.fmt(None) == "time unknown"


def test_demo_cameras_have_curated_details_and_user_edits_win():
    assert cameras.info({}, "camA_west")["location"].startswith("Orchard Road")
    assert cameras.info({"camA_west": {"location": "My street"}}, "camA_west")["location"] == "My street"
    idx = VehicleIndex()
    idx.set_camera("camX", location="Somewhere", start="2026-10-28T10:00:00")
    assert idx.camera("camX")["start"] == "2026-10-28T10:00:00"


def test_gap_formatting():
    assert cameras.fmt_gap(1.24) == "1.2 s"
    assert cameras.fmt_gap(150) == "2 min 30 s"
    assert cameras.fmt_gap(3 * 3600 + 300) == "3 h 05 min"
