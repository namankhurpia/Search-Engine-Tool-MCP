"""End-to-end API tests using the mock provider (no network, no key)."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Force mock provider + auth enabled before the app loads settings.
os.environ["INSIGHT_PROVIDER"] = "mock"
os.environ["INSIGHT_CACHE_ENABLED"] = "false"
os.environ["INSIGHT_AUTH_ENABLED"] = "true"

# Use a temp file for keys so tests don't pollute the real keys.csv.
_tmp_keys = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
os.environ["INSIGHT_KEYS_FILE"] = _tmp_keys.name
_tmp_keys.close()

from insight.keystore import KeyStore  # noqa: E402
from insight.main import app  # noqa: E402

# Create a test key.
_ks = KeyStore(_tmp_keys.name)
_test_record = _ks.create_key("test-agent")
_TEST_KEY = _test_record["key"]
_AUTH = {"Authorization": f"Bearer {_TEST_KEY}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# --- auth tests -------------------------------------------------------------

def test_no_auth_returns_401(client: TestClient):
    r = client.post("/insight", json={"type": "search", "query": "test"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_REQUIRED"


def test_bad_key_returns_403(client: TestClient):
    r = client.post(
        "/insight",
        json={"type": "search", "query": "test"},
        headers={"Authorization": "Bearer ink_bogus"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "INVALID_API_KEY"


def test_health_no_auth_needed(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_types_no_auth_needed(client: TestClient):
    r = client.get("/types")
    assert r.status_code == 200


# --- health & types ---------------------------------------------------------

def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["provider"] == "mock"
    assert body["auth"] is True


def test_types(client: TestClient):
    r = client.get("/types")
    assert r.status_code == 200
    types = r.json()["types"]
    assert "search" in types
    assert "answer" in types
    assert len(types) == 9


# --- raw modes --------------------------------------------------------------

def test_search(client: TestClient):
    r = client.post("/insight", json={"type": "search", "query": "python web frameworks"}, headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "search"
    assert len(body["results"]) > 0
    assert body["sources"]
    assert body["safety_applied"] is True


def test_news(client: TestClient):
    r = client.post("/insight", json={"type": "news", "query": "AI breakthroughs"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["type"] == "news"


def test_deals(client: TestClient):
    r = client.post("/insight", json={"type": "deals", "query": "macbook pro"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["type"] == "deals"


def test_local(client: TestClient):
    r = client.post("/insight", json={"type": "local", "query": "coffee shops"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["type"] == "local"


# --- synth modes ------------------------------------------------------------

def test_answer(client: TestClient):
    r = client.post("/insight", json={"type": "answer", "query": "what is FastAPI?"}, headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "answer"
    assert body["answer"]
    assert body["sources"]


def test_recommend(client: TestClient):
    r = client.post("/insight", json={"type": "recommend", "query": "best headphones under 100"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["answer"]


def test_compare(client: TestClient):
    r = client.post("/insight", json={"type": "compare", "query": "iPhone vs Pixel"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["answer"]


def test_reviews(client: TestClient):
    r = client.post("/insight", json={"type": "reviews", "query": "Sony WH-1000XM5"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["answer"]


def test_alternatives(client: TestClient):
    r = client.post("/insight", json={"type": "alternatives", "query": "Notion"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["answer"]


# --- pagination -------------------------------------------------------------

def test_pagination(client: TestClient):
    r1 = client.post("/insight", json={"type": "search", "query": "test pagination", "page": 1}, headers=_AUTH)
    assert r1.status_code == 200
    body = r1.json()
    assert body["page"] == 1


# --- safety flag ------------------------------------------------------------

def test_safety_off(client: TestClient):
    r = client.post("/insight", json={"type": "search", "query": "test", "safety": False}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["safety_applied"] is False


# --- validation errors ------------------------------------------------------

def test_missing_query(client: TestClient):
    r = client.post("/insight", json={"type": "search"}, headers=_AUTH)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_invalid_type(client: TestClient):
    r = client.post("/insight", json={"type": "invalid", "query": "test"}, headers=_AUTH)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_empty_query(client: TestClient):
    r = client.post("/insight", json={"type": "search", "query": ""}, headers=_AUTH)
    assert r.status_code == 422


# --- keystore unit tests ----------------------------------------------------

def test_keystore_create_and_validate():
    ks = KeyStore(_tmp_keys.name)
    record = ks.create_key("unit-test")
    assert record["key"].startswith("ink_")
    assert ks.validate_key(record["key"]) == "unit-test"


def test_keystore_revoke():
    ks = KeyStore(_tmp_keys.name)
    record = ks.create_key("to-revoke")
    assert ks.validate_key(record["key"]) == "to-revoke"
    assert ks.revoke_key("to-revoke") is True
    assert ks.validate_key(record["key"]) is None


def test_keystore_list_masks_keys():
    ks = KeyStore(_tmp_keys.name)
    keys = ks.list_keys()
    for k in keys:
        assert "..." in k["key"]  # key should be masked
