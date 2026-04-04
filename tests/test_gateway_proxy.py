"""Tests for MCP gateway streaming proxy."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp_oauth_dynamicclient.async_resource_protector import AsyncResourceProtector
from mcp_oauth_dynamicclient.config import Settings
from mcp_oauth_dynamicclient.proxy import create_proxy_router
from mcp_oauth_dynamicclient.service_registry import ServiceEntry, ServiceRegistry


# Mock data
MOCK_SERVICE = ServiceEntry(
    name="fetch",
    public_url="https://fetch.example.com/mcp",
    public_host="fetch.example.com",
    public_base="https://fetch.example.com",
    backend_url="http://100.75.111.118:3000"
)

MOCK_TOKEN = {
    "sub": "12345",
    "username": "testuser",
    "aud": ["https://fetch.example.com"],
    "exp": 9999999999,
    "iat": 1000000000,
}

MOCK_SETTINGS = Settings(
    github_client_id="test",
    github_client_secret="test",
    jwt_secret="test",
    jwt_algorithm="HS256",
    base_domain="example.com",
    auth_subdomain="auth",
    redis_url="redis://localhost",
    redis_password="test",
    access_token_lifetime=1800,
    refresh_token_lifetime=31536000,
    session_timeout=300,
    client_lifetime=7776000,
    allowed_github_users="*",
    mcp_protocol_version="2025-06-18",
)


def create_test_app(
    mock_backend_responses: dict[str, httpx.Response] | None = None,
    mock_token: dict[str, Any] | None = None,
    mock_service: ServiceEntry | None = None,
) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()

    # Mock httpx transport
    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if mock_backend_responses and url in mock_backend_responses:
            return mock_backend_responses[url]

        # Default response
        return httpx.Response(
            status_code=200,
            json={"jsonrpc": "2.0", "result": {"protocolVersion": "2025-06-18"}, "id": 1},
            headers={"Content-Type": "application/json"},
        )

    mock_http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport_handler))

    # Create router
    proxy_router = create_proxy_router(mock_http_client)
    app.include_router(proxy_router)

    # Mock dependencies
    app.state.settings = MOCK_SETTINGS
    app.state.service_registry = MagicMock(spec=ServiceRegistry)
    app.state.require_oauth = MagicMock(spec=AsyncResourceProtector)

    # Override dependency functions
    async def mock_get_service(request):
        return mock_service or MOCK_SERVICE

    async def mock_authenticate(request, service):
        return mock_token or MOCK_TOKEN

    # Replace dependencies
    from mcp_oauth_dynamicclient.proxy import _authenticate, _get_service
    app.dependency_overrides[_get_service] = mock_get_service
    app.dependency_overrides[_authenticate] = mock_authenticate

    return app


def test_post_mcp_proxies_to_backend():
    """Test POST /mcp with valid auth proxies to backend and relays response."""
    backend_response_data = {
        "jsonrpc": "2.0",
        "result": {"protocolVersion": "2025-06-18", "capabilities": {}},
        "id": 1
    }

    mock_backend_responses = {
        "http://100.75.111.118:3000/mcp": httpx.Response(
            status_code=200,
            json=backend_response_data,
            headers={
                "Content-Type": "application/json",
                "Mcp-Session-Id": "session-123",
            }
        )
    }

    app = create_test_app(mock_backend_responses=mock_backend_responses)

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
                "id": 1
            },
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
                "Mcp-Protocol-Version": "2025-06-18",
                "Host": "fetch.example.com",
            }
        )

    assert response.status_code == 200
    assert response.json() == backend_response_data
    assert response.headers.get("mcp-session-id") == "session-123"


def test_get_mcp_sse_stream():
    """Test GET /mcp with valid auth returns SSE stream."""
    # Mock SSE response
    sse_data = "data: {\"jsonrpc\":\"2.0\",\"method\":\"notifications/message\"}\n\n"

    mock_backend_responses = {
        "http://100.75.111.118:3000/mcp": httpx.Response(
            status_code=200,
            content=sse_data.encode(),
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
            }
        )
    }

    app = create_test_app(mock_backend_responses=mock_backend_responses)

    with TestClient(app) as client:
        response = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer test-token",
                "Accept": "text/event-stream",
                "Host": "fetch.example.com",
            }
        )

    assert response.status_code == 200
    assert response.headers.get("content-type") == "text/event-stream"
    assert sse_data in response.text


def test_delete_mcp_terminates_session():
    """Test DELETE /mcp with valid auth terminates session."""
    mock_backend_responses = {
        "http://100.75.111.118:3000/mcp": httpx.Response(
            status_code=204,
            headers={"Content-Type": "application/json"}
        )
    }

    app = create_test_app(mock_backend_responses=mock_backend_responses)

    with TestClient(app) as client:
        response = client.delete(
            "/mcp",
            headers={
                "Authorization": "Bearer test-token",
                "Host": "fetch.example.com",
            }
        )

    assert response.status_code == 204


def test_missing_auth_returns_401():
    """Test POST /mcp with no Authorization header returns 401."""
    app = create_test_app()

    # Mock authentication to raise 401
    async def mock_auth_fail(request, service):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_request", "error_description": "Authorization header required"},
            headers={"WWW-Authenticate": "Bearer"}
        )

    from mcp_oauth_dynamicclient.proxy import _authenticate
    app.dependency_overrides[_authenticate] = mock_auth_fail

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Host": "fetch.example.com"}
        )

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.json()["error"] == "invalid_request"


def test_unknown_host_returns_404():
    """Test POST /mcp with unrecognized Host header returns 404."""
    app = create_test_app()

    # Mock service resolution to return None
    async def mock_service_not_found(request):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_service", "error_description": "No MCP service registered for host: unknown.example.com"}
        )

    from mcp_oauth_dynamicclient.proxy import _get_service
    app.dependency_overrides[_get_service] = mock_service_not_found

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={
                "Authorization": "Bearer test-token",
                "Host": "unknown.example.com"
            }
        )

    assert response.status_code == 404
    assert response.json()["error"] == "unknown_service"


def test_backend_unreachable_returns_502():
    """Test backend ConnectError returns 502 with clear error message."""
    def mock_transport_connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    mock_http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport_connect_error))

    app = create_test_app()
    # Override the router with one using the failing client
    proxy_router = create_proxy_router(mock_http_client)
    app.router.routes.clear()
    app.include_router(proxy_router)

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={
                "Authorization": "Bearer test-token",
                "Host": "fetch.example.com"
            }
        )

    assert response.status_code == 502
    assert response.json()["error"] == "backend_unreachable"
    assert "fetch" in response.json()["error_description"]


def test_backend_timeout_returns_504():
    """Test backend TimeoutException returns 504."""
    def mock_transport_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Request timed out")

    mock_http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport_timeout))

    app = create_test_app()
    # Override the router with one using the timing-out client
    proxy_router = create_proxy_router(mock_http_client)
    app.router.routes.clear()
    app.include_router(proxy_router)

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={
                "Authorization": "Bearer test-token",
                "Host": "fetch.example.com"
            }
        )

    assert response.status_code == 504
    assert response.json()["error"] == "backend_timeout"


def test_health_no_auth_required():
    """Test GET /health without auth is proxied to backend."""
    mock_backend_responses = {
        "http://100.75.111.118:3000/health": httpx.Response(
            status_code=200,
            json={"status": "healthy", "version": "1.0.0"},
            headers={"Content-Type": "application/json"}
        )
    }

    app = create_test_app(mock_backend_responses=mock_backend_responses)

    # Remove auth dependency for health endpoint test
    from mcp_oauth_dynamicclient.proxy import _authenticate
    if _authenticate in app.dependency_overrides:
        del app.dependency_overrides[_authenticate]

    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"Host": "fetch.example.com"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_oauth_protected_resource_dynamic():
    """Test GET /.well-known/oauth-protected-resource returns correct metadata."""
    app = create_test_app()

    # Remove auth dependency for discovery endpoint
    from mcp_oauth_dynamicclient.proxy import _authenticate
    if _authenticate in app.dependency_overrides:
        del app.dependency_overrides[_authenticate]

    with TestClient(app) as client:
        response = client.get(
            "/.well-known/oauth-protected-resource",
            headers={"Host": "fetch.example.com"}
        )

    assert response.status_code == 200
    metadata = response.json()
    assert metadata["resource"] == "https://fetch.example.com"
    assert metadata["authorization_servers"] == ["https://auth.example.com"]
    assert "mcp:read" in metadata["scopes_supported"]
    assert "header" in metadata["bearer_methods_supported"]
    assert response.headers.get("Cache-Control") == "public, max-age=3600"


def test_cors_headers_stripped_from_upstream():
    """Test that CORS headers from upstream are stripped from proxy response."""
    backend_response_data = {"jsonrpc": "2.0", "result": {}, "id": 1}

    mock_backend_responses = {
        "http://100.75.111.118:3000/mcp": httpx.Response(
            status_code=200,
            json=backend_response_data,
            headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization",
                "X-Custom-Header": "should-be-preserved",
            }
        )
    }

    app = create_test_app(mock_backend_responses=mock_backend_responses)

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "test", "id": 1},
            headers={
                "Authorization": "Bearer test-token",
                "Host": "fetch.example.com"
            }
        )

    # CORS headers should be stripped
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-methods" not in response.headers
    assert "access-control-allow-headers" not in response.headers

    # Other headers should be preserved
    assert response.headers.get("x-custom-header") == "should-be-preserved"
    assert response.headers.get("content-type") == "application/json"


def test_user_headers_injected():
    """Test that X-User-Id and X-User-Name are injected from token claims."""
    # We can't directly verify headers sent to backend with TestClient,
    # but we can test the header building function
    from mcp_oauth_dynamicclient.proxy import _build_upstream_headers

    # Mock request with some headers
    mock_request = MagicMock()
    mock_request.headers = {
        "authorization": "Bearer test-token-123",
        "content-type": "application/json",
        "mcp-protocol-version": "2025-06-18",
        "mcp-session-id": "session-456",
        "host": "fetch.example.com",  # Should not be forwarded
    }

    mock_token = {
        "sub": "user-12345",
        "username": "john_doe",
        "aud": ["https://fetch.example.com"],
    }

    headers = _build_upstream_headers(mock_request, mock_token)

    # Verify user headers are injected
    assert headers["x-user-id"] == "user-12345"
    assert headers["x-user-name"] == "john_doe"
    assert headers["x-auth-token"] == "test-token-123"

    # Verify allowed headers are forwarded
    assert headers["content-type"] == "application/json"
    assert headers["mcp-protocol-version"] == "2025-06-18"
    assert headers["mcp-session-id"] == "session-456"

    # Verify disallowed headers are not forwarded
    assert "host" not in headers
    assert "authorization" not in headers


def test_hop_by_hop_headers_stripped():
    """Test that hop-by-hop headers are stripped from upstream response."""
    from mcp_oauth_dynamicclient.proxy import _build_response_headers

    # Mock upstream response headers
    mock_upstream_headers = httpx.Headers({
        "Content-Type": "application/json",
        "Content-Length": "123",
        "Transfer-Encoding": "chunked",  # Should be stripped
        "Connection": "keep-alive",      # Should be stripped
        "Keep-Alive": "timeout=5",       # Should be stripped
        "X-Custom": "value",             # Should be preserved
        "Access-Control-Allow-Origin": "*",  # Should be stripped (CORS)
    })

    result_headers = _build_response_headers(mock_upstream_headers)

    # Verify preserved headers
    assert result_headers["content-type"] == "application/json"
    assert result_headers["content-length"] == "123"
    assert result_headers["x-custom"] == "value"

    # Verify stripped headers
    assert "transfer-encoding" not in result_headers
    assert "connection" not in result_headers
    assert "keep-alive" not in result_headers
    assert "access-control-allow-origin" not in result_headers