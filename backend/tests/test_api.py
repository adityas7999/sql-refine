from contextlib import contextmanager
from unittest.mock import patch

from app import create_app
from config import Config
from connection_manager import parse_connection_settings


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False


class FakeManager:
    def test(self, _settings): return {"serverVersion": "8.0.test"}
    def create_session(self, _settings): return "opaque-session"
    def delete_session(self, _session): pass
    def is_ready(self): return True

    @contextmanager
    def connect(self, _session_id, _database=None):
        yield object()


def client():
    app = create_app(TestConfig)
    app.extensions["connection_manager"] = FakeManager()
    return app.test_client()


def test_health_and_readiness():
    test_client = client()
    assert test_client.get("/api/health").status_code == 200
    assert test_client.get("/api/ready").status_code == 200


def test_connection_response_never_contains_password():
    response = client().post("/api/connection-sessions", json={"host": "localhost", "username": "reader", "password": "super-secret"})
    assert response.status_code == 201
    assert b"super-secret" not in response.data
    assert "password" not in response.get_json()["connection"]


def test_api_returns_structured_validation_errors():
    response = client().post("/api/analyze", json={"database": "shop", "query": "DROP TABLE users"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "READ_ONLY_REQUIRED"


def test_runtime_requires_explicit_confirmation_before_connection_lookup():
    response = client().post("/api/analyze", json={"database": "shop", "query": "SELECT 1", "mode": "runtime"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "RUNTIME_CONFIRMATION_REQUIRED"


def test_plan_mode_does_not_call_runtime_benchmark():
    with patch("routes.query_routes.explain_json", return_value={"query": "SELECT 1", "mode": "plan", "plan": [], "estimatedCost": 1, "runtime": None}) as plan, patch("routes.query_routes.benchmark_pair") as runtime:
        response = client().post("/api/analyze", headers={"X-Connection-Session": "opaque"}, json={"database": "shop", "query": "SELECT 1"})
    assert response.status_code == 200
    plan.assert_called_once()
    runtime.assert_not_called()


def test_unexpected_connection_error_is_redacted():
    test_client = client()
    test_client.application.extensions["connection_manager"].test = lambda _settings: (_ for _ in ()).throw(RuntimeError("password=super-secret"))
    response = test_client.post("/api/connections/test", json={"host": "localhost", "username": "reader", "password": "super-secret"})
    assert response.status_code == 500
    assert b"super-secret" not in response.data
