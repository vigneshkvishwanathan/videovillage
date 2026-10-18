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