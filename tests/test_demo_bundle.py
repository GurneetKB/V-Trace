"""On a fresh deployment (no demo videos, empty index) the app must load the pre-processed demo bundle."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from vtrace import config, index as index_mod  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
pytestmark = pytest.mark.skipif(not (config.DEMO_BUNDLE / "manifest.json").exists(), reason="no demo bundle")


def test_demo_cameras_load_from_bundle_without_videos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VIDEO_DIR", tmp_path / "videos")
    (tmp_path / "videos").mkdir()
    monkeypatch.setattr(index_mod, "INDEX_FILE", tmp_path / "index.pkl")
    monkeypatch.setattr(index_mod.VehicleIndex.load.__func__, "__defaults__", (tmp_path / "index.pkl",))
    monkeypatch.setattr(index_mod.VehicleIndex.save, "__defaults__", (tmp_path / "index.pkl",))

    at = AppTest.from_file(APP, default_timeout=120)
    at.secrets["admin"] = {"username": "admin", "password": "pw"}
    at.run()
    at.text_input[0].input("admin")
    at.text_input[1].input("pw")
    at.button[0].click()
    at.run()
    assert not at.exception
    assert sorted(at.session_state["active"]) == ["camA_west", "camB_centre", "camC_east", "camD_other_road"]
    assert len(at.session_state["view"]) > 100
    assert at.session_state["same_clock"]                       # demo cameras share a clock

    # describe -> ranked matches -> select -> where seen (the demo scenario in docs/DEMO_GUIDE.md)
    at.selectbox[0].select("red")
    at.selectbox[1].select("suv")
    next(b for b in at.button if b.label == "Search").click()
    at.run()
    uids = [r[1]["uid"] for r in at.session_state["results"]]
    assert "camB_centre#156" in uids[:5]
    at.button(key="sel_camB_centre#156").click()
    at.run()
    assert not at.exception
    route = next(m.value for m in at.markdown if m.value.startswith("**Route:**"))
    assert "camA_west (00:40.80)" in route and "camB_centre (00:42.00)" in route and "camC_east (00:43.56)" in route
