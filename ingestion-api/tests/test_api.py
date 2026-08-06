"""Integration tests for the API endpoints."""
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

# Initialize the database pool before importing the app
from database import init_pool
init_pool()

from main import app, limiter

# Disable rate limiting during tests (all tests share same 'testclient' IP)
limiter.enabled = False

client = TestClient(app)

import uuid

def unique_username():
    """Generate a unique username for each test to avoid conflicts across test runs."""
    short_uuid = str(uuid.uuid4())[:8]
    return f"testuser_{short_uuid}"


class TestHealthCheck:
    def test_health_endpoint_exists(self):
        res = client.get("/health")
        assert res.status_code in [200, 503]
        data = res.json()
        assert "status" in data
        assert "database" in data
        assert "ai_models" in data

    def test_health_returns_session_count(self):
        res = client.get("/health")
        data = res.json()
        assert "active_sessions" in data
        assert isinstance(data["active_sessions"], int)


class TestRegistration:
    def test_register_success(self):
        username = unique_username()
        res = client.post("/api/v1/auth/register", json={
            "username": username,
            "password": "securepass123"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "success"

    def test_register_duplicate_username(self):
        username = unique_username()
        # First registration
        client.post("/api/v1/auth/register", json={
            "username": username,
            "password": "securepass123"
        })
        # Second registration with same username
        res = client.post("/api/v1/auth/register", json={
            "username": username,
            "password": "differentpass123"
        })
        assert res.status_code == 400
        assert "already taken" in res.json()["detail"].lower()

    def test_register_short_username(self):
        res = client.post("/api/v1/auth/register", json={
            "username": "ab",
            "password": "securepass123"
        })
        assert res.status_code == 422  # Pydantic validation error

    def test_register_short_password(self):
        res = client.post("/api/v1/auth/register", json={
            "username": unique_username(),
            "password": "short"
        })
        assert res.status_code == 422

    def test_register_reserved_username(self):
        res = client.post("/api/v1/auth/register", json={
            "username": "admin",
            "password": "securepass123"
        })
        assert res.status_code == 422

    def test_register_invalid_characters(self):
        res = client.post("/api/v1/auth/register", json={
            "username": "user@name!",
            "password": "securepass123"
        })
        assert res.status_code == 422


class TestLogin:
    @pytest.fixture(autouse=True)
    def setup_user(self):
        """Create a test user before each login test."""
        self.username = unique_username()
        self.password = "testpassword123"
        client.post("/api/v1/auth/register", json={
            "username": self.username,
            "password": self.password
        })

    def test_login_success_returns_tokens(self):
        res = client.post("/api/v1/auth/login", json={
            "username": self.username,
            "password": self.password
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "days_until_expiry" in data

    def test_login_wrong_password(self):
        res = client.post("/api/v1/auth/login", json={
            "username": self.username,
            "password": "wrongpassword123"
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self):
        res = client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user_xyz",
            "password": "anypassword123"
        })
        assert res.status_code == 401


class TestTokenRefresh:
    def test_refresh_returns_new_access_token(self):
        username = unique_username()
        client.post("/api/v1/auth/register", json={
            "username": username, "password": "testpassword123"
        })
        login_res = client.post("/api/v1/auth/login", json={
            "username": username, "password": "testpassword123"
        })
        refresh_token = login_res.json()["refresh_token"]
        
        res = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_refresh_with_invalid_token(self):
        res = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.here"
        })
        assert res.status_code == 401


class TestProtectedRoutes:
    def _get_token(self):
        """Helper: register + login and return access token."""
        username = unique_username()
        client.post("/api/v1/auth/register", json={
            "username": username, "password": "testpassword123"
        })
        login_res = client.post("/api/v1/auth/login", json={
            "username": username, "password": "testpassword123"
        })
        return login_res.json()["access_token"]

    def test_admin_requires_auth(self):
        res = client.get("/api/v1/admin/sessions")
        assert res.status_code == 401

    def test_admin_with_valid_token(self):
        token = self._get_token()
        res = client.get("/api/v1/admin/sessions", headers={
            "Authorization": f"Bearer {token}"
        })
        assert res.status_code == 200
        assert "active_sessions" in res.json()

    def test_admin_with_invalid_token(self):
        res = client.get("/api/v1/admin/sessions", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert res.status_code == 401

    def test_profile_endpoint(self):
        token = self._get_token()
        res = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "username" in data
        assert "days_until_expiry" in data

    def test_regenerate_requires_auth(self):
        res = client.post("/api/v1/auth/regenerate")
        assert res.status_code == 401

    def test_regenerate_with_valid_token(self):
        token = self._get_token()
        res = client.post("/api/v1/auth/regenerate", headers={
            "Authorization": f"Bearer {token}"
        })
        assert res.status_code == 200
        data = res.json()
        assert "new_password" in data
        assert len(data["new_password"]) == 16  # We generate 16-char passwords
        assert data["days_until_expiry"] == 90


class TestIngest:
    def test_ingest_requires_api_key(self):
        res = client.post("/api/v1/ingest", json={
            "session_id": "test-session-001",
            "timestamp_start": 1000,
            "timestamp_end": 6000,
            "device_context": {
                "user_agent": "test",
                "screen_resolution": "1920x1080",
                "platform": "macOS"
            },
            "events": {
                "keystrokes": [],
                "mouse_movements": [],
                "clicks": [],
                "scrolls": []
            }
        })
        assert res.status_code == 401

    def test_ingest_with_valid_api_key(self):
        res = client.post("/api/v1/ingest", 
            json={
                "session_id": "test-session-002",
                "timestamp_start": 1000,
                "timestamp_end": 6000,
                "device_context": {
                    "user_agent": "test",
                    "screen_resolution": "1920x1080",
                    "platform": "macOS"
                },
                "events": {
                    "keystrokes": [],
                    "mouse_movements": [],
                    "clicks": [],
                    "scrolls": []
                }
            },
            headers={"x-api-key": "sk_live_51Mabcde12345"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert res.json()["security_action"] == "allow"

    def test_ingest_with_invalid_api_key(self):
        res = client.post("/api/v1/ingest",
            json={
                "session_id": "test-session-003",
                "timestamp_start": 1000,
                "timestamp_end": 6000,
                "device_context": {
                    "user_agent": "test",
                    "screen_resolution": "1920x1080",
                    "platform": "macOS"
                },
                "events": {
                    "keystrokes": [],
                    "mouse_movements": [],
                    "clicks": [],
                    "scrolls": []
                }
            },
            headers={"x-api-key": "invalid_key_12345"}
        )
        assert res.status_code == 401


class TestCalibration:
    def test_calibrate_requires_api_key(self):
        res = client.post("/api/v1/calibrate/complete", json={
            "session_id": "test-session-cal"
        })
        assert res.status_code == 401
