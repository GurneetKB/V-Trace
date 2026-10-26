from vtrace import config, search
from vtrace.index import VehicleIndex


def test_description_search_ranks_matching_vehicle_first(make_tracklet):
    idx = VehicleIndex([
        make_tracklet("a#1", "a", color="white", vtype="suv", plate="SGX1234A"),
        make_tracklet("a#2", "a", color="red", vtype="sedan", plate="SBA9876C"),
        make_tracklet("b#1", "b", color="black", vtype="van"),
    ])
    res = search.describe_search(idx, color="white", vtype="suv", plate="SGX12??")
    assert res[0][1]["uid"] == "a#1"
    assert set(res[0][2]) == {"color", "type", "plate"}  # only the provided fields are scored


def test_missing_fields_do_not_block_retrieval(make_tracklet):
    idx = VehicleIndex([make_tracklet("a#1", "a"), make_tracklet("b#1", "b")])
    assert len(search.describe_search(idx)) == 2
    assert len(search.describe_search(idx, color="white")) == 2


def test_unread_plate_gets_neutral_score(make_tracklet):
    t = make_tracklet("a#1", "a", plate="")
    s = search.field_scores(t, plate="SGX1234A")
    assert s["plate"] == config.UNREAD_PLATE_SCORE


def test_video_filter(make_tracklet):
    idx = VehicleIndex([make_tracklet("a#1", "a"), make_tracklet("b#1", "b")])
    res = search.describe_search(idx, color="white", videos=["b"])
    assert [r[1]["uid"] for r in res] == ["b#1"]
