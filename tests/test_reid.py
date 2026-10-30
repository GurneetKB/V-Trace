from vtrace import reid
from vtrace.index import VehicleIndex


def _timed(t, start, end):
    t.update(start_t=start, end_t=end, best_t=(start + end) / 2)
    return t


def scene(make_tracklet):
    """car1 passes camA, camB and camC; car2 only camA and camB; camD sees a different vehicle much later."""
    return VehicleIndex([_timed(make_tracklet("A#1", "camA", "car1"), 0, 2),
                         _timed(make_tracklet("A#2", "camA", "car2", color="red", vtype="sedan"), 0, 2),
                         _timed(make_tracklet("C#1", "camC", "car1"), 6, 8),
                         _timed(make_tracklet("B#1", "camB", "car1"), 3, 5),
                         _timed(make_tracklet("B#2", "camB", "car2", color="red", vtype="sedan"), 3, 5),
                         _timed(make_tracklet("D#9", "camD", "other", color="black", vtype="van"), 30, 35)])


def test_rank_puts_same_vehicle_first_and_skips_own_camera(make_tracklet):
    idx = scene(make_tracklet)
    hits = reid.rank(idx, idx.get("A#1"))
    assert {t["uid"] for _, t in hits[:2]} == {"B#1", "C#1"}
    assert all(t["video"] != "camA" for _, t in hits)


def test_where_seen_lists_every_camera_with_the_vehicle(make_tracklet):
    idx = scene(make_tracklet)
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5)
    assert set(seen) == {"camA", "camB", "camC", "camD"}
    assert {v: s["match"] and s["match"][1]["uid"] for v, s in seen.items()} == \
        {"camA": "A#1", "camB": "B#1", "camC": "C#1", "camD": None}
    assert seen["camD"]["candidates"][0][1]["uid"] == "D#9"         # closest vehicle shown when there is no match
    assert [t["uid"] for t in reid.route(seen)] == ["A#1", "B#1", "C#1"]


def test_ambiguous_camera_is_left_to_the_user(make_tracklet):
    idx = scene(make_tracklet)
    idx.tracklets.append(_timed(make_tracklet("B#3", "camB", "car1"), 3, 5))   # a second, equally similar sighting
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5, margin=0.08)
    assert seen["camB"]["match"] is None and seen["camC"]["match"] is not None


def test_time_window(make_tracklet):
    idx = scene(make_tracklet)
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5, max_gap_s=3)
    assert seen["camB"]["match"] is not None and seen["camC"]["match"] is None     # camC is 4 s later
    assert seen["camD"]["candidates"] == []


def test_threshold(make_tracklet):
    idx = scene(make_tracklet)
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=1.01)
    assert [v for v, s in seen.items() if s["match"]] == ["camA"]
