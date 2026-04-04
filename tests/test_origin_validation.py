"""Tests for origin validation middleware."""

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../mcp-oauth-dynamicclient/src"))

from mcp_oauth_dynamicclient.origin_middleware import OriginValidationMiddleware

pytestmark = pytest.mark.local_only


@pytest.fixture
def test_app():
    """Create a minimal test app with the origin validation middleware."""
    app = FastAPI()

    # Add the origin validation middleware
    app.add_middleware(OriginValidationMiddleware)

    # Add test routes for different path types
    @app.get("/mcp")
    async def mcp_endpoint():
        return {"message": "mcp endpoint"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    @app.get("/session/test")
    async def session_endpoint():
        return {"message": "session endpoint"}

    @app.get("/sessions/list")
    async def sessions_endpoint():
        return {"message": "sessions endpoint"}

    # OAuth endpoints (should skip validation)
    @app.post("/register")
    async def register_endpoint():
        return {"message": "register endpoint"}

    @app.get("/authorize")
    async def authorize_endpoint():
        return {"message": "authorize endpoint"}

    @app.post("/token")
    async def token_endpoint():
        return {"message": "token endpoint"}

    @app.get("/.well-known/oauth-authorization-server")
    async def well_known_endpoint():
        return {"message": "well-known endpoint"}

    @app.get("/register/client123")
    async def register_management_endpoint():
        return {"message": "register management endpoint"}

    @app.get("/other")
    async def other_endpoint():
        return {"message": "other endpoint"}

    return app


@pytest.fixture
def test_app_with_custom_origins():
    """Create a test app with custom allowed origins."""
    app = FastAPI()

    # Add middleware with custom origins
    app.add_middleware(OriginValidationMiddleware, allowed_origins_str="myapp.io,example.com")

    @app.get("/mcp")
    async def mcp_endpoint():
        return {"message": "mcp endpoint"}

    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def custom_client(test_app_with_custom_origins):
    """Create test client with custom origins."""
    return TestClient(test_app_with_custom_origins)


class TestOriginValidation:
    """Test origin validation middleware behavior."""

    def test_empty_origin_allowed(self, client):
        """Request to /mcp with no Origin header should be allowed."""
        response = client.get("/mcp")
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_matching_server_origin_allowed(self, client):
        """Origin matching server name should be allowed."""
        headers = {
            "origin": "https://fetch.example.com",
            "host": "fetch.example.com"
        }
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_matching_server_origin_with_port(self, client):
        """Origin matching server name should work with port in host."""
        headers = {
            "origin": "https://fetch.example.com",
            "host": "fetch.example.com:443"
        }
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_localhost_http_allowed(self, client):
        """Origin with localhost HTTP should be allowed."""
        headers = {"origin": "http://localhost:3000"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_localhost_https_allowed(self, client):
        """Origin with localhost HTTPS should be allowed."""
        headers = {"origin": "https://localhost:8080"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_localhost_no_port_allowed(self, client):
        """Origin with localhost without port should be allowed."""
        headers = {"origin": "http://localhost"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_127_0_0_1_allowed(self, client):
        """Origin with 127.0.0.1 should be allowed."""
        headers = {"origin": "http://127.0.0.1:5000"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_127_0_0_1_https_allowed(self, client):
        """Origin with 127.0.0.1 HTTPS should be allowed."""
        headers = {"origin": "https://127.0.0.1:9000"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_anthropic_allowed(self, client):
        """Origin with anthropic.com subdomain should be allowed."""
        headers = {"origin": "https://proxy.anthropic.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_anthropic_root_allowed(self, client):
        """Origin with anthropic.com root should be allowed."""
        headers = {"origin": "https://anthropic.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_claude_ai_allowed(self, client):
        """Origin with claude.ai should be allowed."""
        headers = {"origin": "https://claude.ai"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_claude_subdomain_allowed(self, client):
        """Origin with claude.ai subdomain should be allowed."""
        headers = {"origin": "https://app.claude.ai"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_evil_origin_rejected(self, client):
        """Origin with evil domain should be rejected."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403
        assert response.json() == {
            "error": "origin_not_allowed",
            "message": "Origin header validation failed"
        }

    def test_evil_origin_anthropic_subdomain_rejected(self, client):
        """Evil domain pretending to be anthropic subdomain should be rejected."""
        headers = {"origin": "https://evil.anthropic.com.evil.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403

    def test_evil_origin_claude_subdomain_rejected(self, client):
        """Evil domain pretending to be claude subdomain should be rejected."""
        headers = {"origin": "https://evil.claude.ai.evil.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403

    def test_custom_allowed_origins(self, custom_client):
        """Custom allowed origins should work."""
        headers = {"origin": "https://myapp.io"}
        response = custom_client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_custom_subdomain_allowed(self, custom_client):
        """Custom allowed origins should work with subdomains."""
        headers = {"origin": "https://sub.myapp.io"}
        response = custom_client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_custom_second_domain_allowed(self, custom_client):
        """Second custom domain should work."""
        headers = {"origin": "https://example.com"}
        response = custom_client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}

    def test_custom_origins_still_allow_defaults(self, custom_client):
        """Custom origins should not override default allowlist."""
        headers = {"origin": "https://anthropic.com"}
        response = custom_client.get("/mcp", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "mcp endpoint"}


class TestOAuthEndpointsSkipValidation:
    """Test that OAuth endpoints skip origin validation."""

    def test_register_skip_validation(self, client):
        """POST /register should skip origin validation even for evil origins."""
        headers = {"origin": "https://evil.com"}
        response = client.post("/register", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "register endpoint"}

    def test_authorize_skip_validation(self, client):
        """GET /authorize should skip origin validation."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/authorize", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "authorize endpoint"}

    def test_token_skip_validation(self, client):
        """POST /token should skip origin validation."""
        headers = {"origin": "https://evil.com"}
        response = client.post("/token", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "token endpoint"}

    def test_wellknown_skip_validation(self, client):
        """/.well-known/oauth-authorization-server should skip origin validation."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/.well-known/oauth-authorization-server", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "well-known endpoint"}

    def test_register_management_skip_validation(self, client):
        """RFC 7592 client management endpoints should skip origin validation."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/register/client123", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "register management endpoint"}


class TestProtectedPaths:
    """Test that protected paths validate origin correctly."""

    def test_health_endpoint_validated(self, client):
        """Health endpoint should validate origin."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/health", headers=headers)
        assert response.status_code == 403
        assert response.json() == {
            "error": "origin_not_allowed",
            "message": "Origin header validation failed"
        }

    def test_health_endpoint_allowed_origin(self, client):
        """Health endpoint should allow good origins."""
        headers = {"origin": "https://claude.ai"}
        response = client.get("/health", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_session_endpoint_validated(self, client):
        """Session endpoints should validate origin."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/session/test", headers=headers)
        assert response.status_code == 403

    def test_sessions_endpoint_validated(self, client):
        """Sessions endpoints should validate origin."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/sessions/list", headers=headers)
        assert response.status_code == 403

    def test_session_endpoint_allowed_origin(self, client):
        """Session endpoints should allow good origins."""
        headers = {"origin": "https://anthropic.com"}
        response = client.get("/session/test", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "session endpoint"}

    def test_other_paths_not_validated(self, client):
        """Paths not in protected list should not be validated."""
        headers = {"origin": "https://evil.com"}
        response = client.get("/other", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "other endpoint"}


class TestEdgeCases:
    """Test edge cases and malformed inputs."""

    def test_malformed_origin_rejected(self, client):
        """Malformed origin headers should be rejected."""
        headers = {"origin": "not-a-url"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403

    def test_http_anthropic_rejected(self, client):
        """HTTP origins for HTTPS-only domains should be rejected."""
        headers = {"origin": "http://anthropic.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403

    def test_anthropic_with_path_rejected(self, client):
        """Origins with paths should be rejected."""
        headers = {"origin": "https://anthropic.com/path"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403

    def test_empty_host_header(self, client):
        """Empty host header should not crash the middleware."""
        headers = {"origin": "https://example.com", "host": ""}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403  # Should reject since host doesn't match

    def test_missing_host_header(self, client):
        """Missing host header should not crash the middleware."""
        headers = {"origin": "https://example.com"}
        # Remove default host header that TestClient adds
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 403  # Should reject since no host to match

    def test_custom_origins_empty_string(self):
        """Empty string for custom origins should use defaults only."""
        app = FastAPI()
        app.add_middleware(OriginValidationMiddleware, allowed_origins_str="")

        @app.get("/mcp")
        async def mcp_endpoint():
            return {"message": "mcp endpoint"}

        client = TestClient(app)

        # Should still allow default patterns
        headers = {"origin": "https://claude.ai"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200

    def test_custom_origins_whitespace_handling(self):
        """Whitespace in custom origins should be handled correctly."""
        app = FastAPI()
        app.add_middleware(OriginValidationMiddleware, allowed_origins_str=" test.com , example.org ")

        @app.get("/mcp")
        async def mcp_endpoint():
            return {"message": "mcp endpoint"}

        client = TestClient(app)

        # Should trim whitespace and work
        headers = {"origin": "https://test.com"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200

        headers = {"origin": "https://example.org"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code == 200