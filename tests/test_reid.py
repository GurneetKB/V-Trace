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


def _clocked(idx, starts):
    """Give each camera a real-world recording start (ISO strings) and attach real-world times."""
    from vtrace import cameras
    cams = {v: {"start": st} for v, st in starts.items()}
    cameras.apply(idx.tracklets, cams)
    return idx


def test_time_window_uses_real_world_time(make_tracklet):
    same = {"camA": "2026-10-28T08:00:00", "camB": "2026-10-28T08:00:00", "camC": "2026-10-28T08:00:00",
            "camD": "2026-10-28T08:00:00"}
    idx = _clocked(scene(make_tracklet), same)
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5, max_gap_s=3)
    assert seen["camB"]["match"] is not None and seen["camC"]["match"] is None     # camC is 4 s later
    assert seen["camD"]["candidates"] == []

    # camC's video started 2 minutes earlier: in real-world time its sighting is now before camA's, 2 min apart
    idx = _clocked(scene(make_tracklet), same | {"camC": "2026-10-28T07:58:00"})
    assert reid.gap(idx.get("A#1"), idx.get("C#1")) == 112                     # 08:00:00 - 07:58:08
    assert reid.where_seen(idx, idx.get("A#1"), threshold=0.5, max_gap_s=60)["camC"]["match"] is None
    assert reid.where_seen(idx, idx.get("A#1"), threshold=0.5, max_gap_s=300)["camC"]["match"] is not None


def test_unknown_recording_start_is_not_time_limited(make_tracklet):
    idx = scene(make_tracklet)                                                     # no camera details at all
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5, max_gap_s=1)
    assert seen["camC"]["match"] is not None


def test_route_is_in_real_world_order(make_tracklet):
    idx = _clocked(scene(make_tracklet), {"camA": "2026-10-28T09:00:00", "camB": "2026-10-28T08:00:00",
                                          "camC": "2026-10-28T08:30:00", "camD": "2026-10-28T08:00:00"})
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=0.5)
    assert [t["video"] for t in reid.route(seen)] == ["camB", "camC", "camA"]


def test_threshold(make_tracklet):
    idx = scene(make_tracklet)
    seen = reid.where_seen(idx, idx.get("A#1"), threshold=1.01)
    assert [v for v, s in seen.items() if s["match"]] == ["camA"]
