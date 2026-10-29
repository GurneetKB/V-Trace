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
    assert len(at.session_state["view"]) == 187
