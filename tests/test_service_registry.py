"""Tests for service registry."""

import os
from unittest.mock import patch

import pytest

from mcp_oauth_dynamicclient.service_registry import ServiceEntry, ServiceRegistry


@pytest.mark.local_only
def test_registry_parses_enabled_services():
    """Test that registry correctly parses enabled services with all required env vars."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 1
        service = registry.resolve("fetch.example.com")
        assert service is not None
        assert service.name == "fetch"
        assert service.public_url == "https://fetch.example.com/mcp"
        assert service.public_host == "fetch.example.com"
        assert service.public_base == "https://fetch.example.com"
        assert service.backend_url == "http://100.1.2.3:3000"


@pytest.mark.local_only
def test_registry_skips_disabled_services():
    """Test that registry skips services that are not enabled."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'false',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 0


@pytest.mark.local_only
def test_registry_warns_on_missing_backend(caplog):
    """Test that registry warns and skips services missing backend URL."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp'
        # Missing MCP_FETCH_BACKEND
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 0
        assert "Service fetch enabled but missing MCP_FETCH_BACKEND" in caplog.text


@pytest.mark.local_only
def test_registry_multiple_services():
    """Test that registry handles multiple enabled services correctly."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000',
        'MCP_ECHO_STATEFUL_ENABLED': 'true',
        'MCP_ECHO_STATEFUL_URLS': 'https://echo.example.com/mcp',
        'MCP_ECHO_STATEFUL_BACKEND': 'http://100.1.2.4:3001',
        'MCP_FILESYSTEM_ENABLED': 'true',
        'MCP_FILESYSTEM_URLS': 'https://fs.example.com/mcp',
        'MCP_FILESYSTEM_BACKEND': 'http://100.1.2.5:3002'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 3

        fetch_service = registry.resolve("fetch.example.com")
        assert fetch_service is not None
        assert fetch_service.name == "fetch"
        assert fetch_service.backend_url == "http://100.1.2.3:3000"

        echo_service = registry.resolve("echo.example.com")
        assert echo_service is not None
        assert echo_service.name == "echo_stateful"
        assert echo_service.backend_url == "http://100.1.2.4:3001"

        fs_service = registry.resolve("fs.example.com")
        assert fs_service is not None
        assert fs_service.name == "filesystem"
        assert fs_service.backend_url == "http://100.1.2.5:3002"


@pytest.mark.local_only
def test_resolve_strips_port():
    """Test that resolve strips port from host header before lookup."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        # Test with explicit port
        service = registry.resolve("fetch.example.com:443")
        assert service is not None
        assert service.name == "fetch"

        # Test with non-standard port
        service = registry.resolve("fetch.example.com:8080")
        assert service is not None
        assert service.name == "fetch"


@pytest.mark.local_only
def test_resolve_unknown_host_returns_none():
    """Test that resolve returns None for unknown hosts."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        service = registry.resolve("unknown.example.com")
        assert service is None


@pytest.mark.local_only
def test_all_services_returns_list():
    """Test that all_services returns list of all registered services."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000',
        'MCP_ECHO_STATEFUL_ENABLED': 'true',
        'MCP_ECHO_STATEFUL_URLS': 'https://echo.example.com/mcp',
        'MCP_ECHO_STATEFUL_BACKEND': 'http://100.1.2.4:3001'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        all_services = registry.all_services()
        assert len(all_services) == 2

        service_names = {service.name for service in all_services}
        assert service_names == {"fetch", "echo_stateful"}


@pytest.mark.local_only
def test_registry_case_insensitive_enabled():
    """Test that registry recognizes enabled services with different case."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'True',  # Capital T
        'MCP_FETCH_URLS': 'https://fetch.example.com/mcp',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 1
        service = registry.resolve("fetch.example.com")
        assert service is not None
        assert service.name == "fetch"


@pytest.mark.local_only
def test_registry_warns_on_missing_urls(caplog):
    """Test that registry warns and skips services missing URLs."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
        # Missing MCP_FETCH_URLS
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 0
        assert "Service fetch enabled but missing MCP_FETCH_URLS" in caplog.text


@pytest.mark.local_only
def test_registry_handles_invalid_url(caplog):
    """Test that registry handles invalid URLs gracefully."""
    env_vars = {
        'MCP_FETCH_ENABLED': 'true',
        'MCP_FETCH_URLS': 'not-a-valid-url',
        'MCP_FETCH_BACKEND': 'http://100.1.2.3:3000'
    }

    with patch.dict(os.environ, env_vars, clear=False):
        registry = ServiceRegistry()

        assert len(registry) == 0
        assert ("has invalid public URL" in caplog.text
                or "Failed to parse public URL" in caplog.text)


@pytest.mark.local_only
def test_service_entry_immutable():
    """Test that ServiceEntry is immutable (frozen dataclass)."""
    entry = ServiceEntry(
        name="test",
        public_url="https://test.example.com/mcp",
        public_host="test.example.com",
        public_base="https://test.example.com",
        backend_url="http://100.1.2.3:3000"
    )

    with pytest.raises(AttributeError):
        entry.name = "modified"  # Should fail because dataclass is frozen
