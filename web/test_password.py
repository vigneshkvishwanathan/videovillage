import os

os.environ.setdefault("DATABASE_URL", "postgresql://not-used-by-these-tests")

from app import app  # noqa: E402  (the line above has to run first)

# /discs/search with no query touches neither the database nor TMDb,
# so it's a safe page for checking the password gate on its own.
PAGE = "/discs/search"


def test_no_password_set_means_no_gate(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert app.test_client().get(PAGE).status_code == 200


def test_missing_password_is_refused(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    response = app.test_client().get(PAGE)
    assert response.status_code == 401
    assert "Basic" in response.headers["WWW-Authenticate"]


def test_wrong_password_is_refused(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    response = app.test_client().get(PAGE, auth=("brother", "guess"))
    assert response.status_code == 401


def test_right_password_gets_in(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    response = app.test_client().get(PAGE, auth=("brother", "letmein"))
    assert response.status_code == 200


def test_health_check_skips_the_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.data == b"ok"

# Browsing is public; anything that changes data (or uses TMDb) is locked.
from app import needs_password  # noqa: E402


def test_browsing_pages_are_public():
    for page in ("index", "search_page", "show_disc", "static", "health"):
        assert not needs_password(page, "GET")


def test_changes_need_the_password():
    for page in ("add_disc", "edit_disc", "add_viewing", "mark_owned",
                 "delete_disc", "search_tmdb"):
        assert needs_password(page, "GET") or needs_password(page, "POST")
        assert needs_password(page, "POST")


def test_posting_to_a_public_page_still_needs_the_password():
    assert needs_password("index", "POST")


def test_unknown_routes_are_locked_by_default():
    assert needs_password("some_future_page", "GET")
    assert needs_password(None, "GET")


def test_delete_without_password_is_refused(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    response = app.test_client().post("/discs/1/delete")
    assert response.status_code == 401


def test_stylesheet_loads_without_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "letmein")
    assert app.test_client().get("/static/style.css").status_code == 200
