import numpy as np
import pytest

from vtrace import config, reid
from vtrace.index import VehicleIndex


@pytest.fixture
def scene(make_tracklet):
    """Camera A sees vehicle X; camera B sees X again plus two distractors."""
    return VehicleIndex([
        make_tracklet("A#1", "A", vehicle="X", plate="SGX1234A"),
        make_tracklet("A#2", "A", vehicle="X2"),
        make_tracklet("B#1", "B", vehicle="Y", color="white", vtype="suv"),
        make_tracklet("B#2", "B", vehicle="X", plate="SGX1234A"),
        make_tracklet("B#3", "B", vehicle="Z", color="black", vtype="sedan"),
    ])


def test_pair_features_match_config(scene):
    f = reid.pair_features(scene.tracklets[0], scene.tracklets[3])
    assert list(f) == config.PAIR_FEATURES
    assert f["plate_avail"] == 1.0 and f["plate_sim"] == 1.0
    assert f["app_cos"] > 0.9


def test_weighted_fusion_ignores_plate_when_unreadable(scene):
    f = reid.pair_features(scene.tracklets[0], scene.tracklets[2])   # B#1 has no plate
    assert f["plate_avail"] == 0.0
    w = {k: v for k, v in config.FUSION_WEIGHTS.items() if k != "plate_sim"}
    expected = sum(w[k] * f[k] for k in w) / sum(w.values())
    assert reid.weighted_fusion(f) == pytest.approx(expected)


@pytest.mark.parametrize("method", ["appearance only", "weighted fusion", "random forest"])
def test_reid_finds_true_match_in_other_video(scene, method):
    hits = reid.reid_search(scene, scene.tracklets[0], method=method, rf=None)
    assert hits[0][1]["uid"] == "B#2"
    assert all(h[1]["video"] != "A" for h in hits)                  # other videos only


def test_include_same_video(scene):
    hits = reid.reid_search(scene, scene.tracklets[0], include_same_video=True)
    assert "A#2" in {h[1]["uid"] for h in hits}


def test_random_forest_learns_same_vs_different(make_tracklet):
    pos = [reid.pair_features(make_tracklet(f"p{i}a", "A", vehicle=f"v{i}"),
                              make_tracklet(f"p{i}b", "B", vehicle=f"v{i}")) for i in range(30)]
    neg = [reid.pair_features(make_tracklet(f"n{i}a", "A"), make_tracklet(f"n{i}b", "B")) for i in range(30)]
    X, y = reid.to_matrix(pos + neg), np.array([1] * 30 + [0] * 30)
    rf = reid.train_rf(X, y)
    scores = reid.score_pairs(pos[:5] + neg[:5], "random forest", rf)
    assert scores[:5].min() > scores[5:].max()


def test_single_cue_ablation(scene):
    feats = [reid.pair_features(scene.tracklets[0], t) for t in scene.tracklets[2:]]
    assert np.allclose(reid.score_pairs(feats, "app_cos"), [f["app_cos"] for f in feats])


def _timed(t, start, end):
    t.update(start_t=start, end_t=end, best_t=(start + end) / 2)
    return t


def test_trace_path_follows_vehicle_across_cameras(make_tracklet):
    from vtrace.index import VehicleIndex
    idx = VehicleIndex()
    idx.tracklets = [_timed(make_tracklet("A#1", "camA", "car1"), 0, 2),
                     _timed(make_tracklet("A#2", "camA", "car2", color="red", vtype="sedan"), 0, 2),
                     _timed(make_tracklet("C#1", "camC", "car1"), 6, 8),
                     _timed(make_tracklet("B#1", "camB", "car1"), 3, 5),
                     _timed(make_tracklet("B#2", "camB", "car2", color="red", vtype="sedan"), 3, 5),
                     _timed(make_tracklet("D#9", "camD", "other", color="black", vtype="van"), 3, 5)]
    path = reid.trace_path(idx, idx.tracklets[0], "weighted fusion", min_score=0.7)
    assert [t["uid"] for _, t in path] == ["A#1", "B#1", "C#1"]      # time order, one per camera, no camD


def test_trace_path_time_window(make_tracklet):
    from vtrace.index import VehicleIndex
    idx = VehicleIndex()
    idx.tracklets = [_timed(make_tracklet("A#1", "camA", "car1"), 0, 2),
                     _timed(make_tracklet("B#1", "camB", "car1"), 100, 102)]
    assert len(reid.trace_path(idx, idx.tracklets[0], "weighted fusion", 0.7, max_gap_s=15)) == 1
    assert len(reid.trace_path(idx, idx.tracklets[0], "weighted fusion", 0.7, max_gap_s=None)) == 2
