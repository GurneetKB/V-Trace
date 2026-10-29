"""The admin sign-in page must keep the app locked until the right username and password are given."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def make_app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["admin"] = {"username": "admin", "password": "test-pass"}
    return at.run()


def sign_in(at, user, pwd):
    at.text_input[0].input(user)
    at.text_input[1].input(pwd)
    at.button[0].click()
    return at.run()


def test_locked_until_signed_in():
    at = make_app()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Username", "Password"]
    assert len(at.tabs) == 0


def test_wrong_password_rejected():
    at = sign_in(make_app(), "admin", "nope")
    assert "Incorrect username or password." in [e.value for e in at.error]
    assert len(at.tabs) == 0
    assert "admin_user" not in at.session_state


def test_right_password_opens_app_and_sign_out_locks_it():
    at = sign_in(make_app(), "admin", "test-pass")
    assert not at.exception
    assert len(at.tabs) == 6
    at.sidebar.button[0].click()            # Sign out
    at.run()
    assert len(at.tabs) == 0
