"""Tests for the MCP server tool layer.

These test the server.py wrapper — tool functions that call the client,
serialize results to JSON strings, and handle errors. The client itself is
mocked so we isolate the wrapping logic.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

os.environ.setdefault("OPENGIST_URL", "https://paste.test.local")
os.environ.setdefault("OPENGIST_TOKEN", "og_testtoken")

from opengist_mcp import server
from opengist_mcp.client import OpengistError, Page


def _parse(result: str) -> dict:
    return json.loads(result)


def _gist(uuid="abc123"):
    return {
        "id": uuid,
        "title": "Test",
        "visibility": "public",
        "files": {"readme.md": {"content": "# Hello"}},
    }


# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:
    def test_returns_version_and_config(self):
        result = _parse(server.health())
        assert result["ok"] is True
        assert result["version"] == "0.1.0"


# ── Env var resolution ────────────────────────────────────────────────────────


class TestEnvResolution:
    def setup_method(self):
        server._client = None

    @patch.dict(
        os.environ,
        {"OPENGIST_URL": "https://custom.example.com", "OPENGIST_TOKEN": "og_custom"},
    )
    def test_get_client_uses_env_vars(self):
        client = server._get_client()
        assert client._base_url == "https://custom.example.com"
        assert client._default_token == "og_custom"

    @patch.dict(
        os.environ,
        {"OPENGIST_URL": "https://custom.example.com", "OPENGIST_TIMEOUT": "60"},
        clear=False,
    )
    def test_timeout_env_var(self):
        server._client = None
        client = server._get_client()
        assert client._timeout == 60

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_url_raises(self):
        server._client = None
        with pytest.raises(OpengistError, match="OPENGIST_URL"):
            server._get_client()


# ── Token delivery regression (C1) ────────────────────────────────────────────


class TestTokenDelivery:
    """Regression test for C1: token must reach the HTTP Authorization header
    via per-method forwarding, NOT via mutating the singleton's _default_token.

    Uses respx (transport-level mock) + real OpengistClient to verify the token
    flows through to the wire."""

    def setup_method(self):
        server._client = None

    def test_per_call_token_reaches_http_header(self):
        with respx.mock(base_url="https://paste.test.local") as mock:
            route = mock.get("/api/gists/abc").mock(
                return_value=httpx.Response(200, json=_gist("abc"))
            )
            server._get_client()
            server.get_gist("abc", token="og_USER_A")
            assert route.calls[0].request.headers["authorization"] == "Bearer og_USER_A"

    def test_interleaved_calls_keep_correct_tokens(self):
        with respx.mock(base_url="https://paste.test.local") as mock:
            route_a = mock.get("/api/gists/aaa").mock(
                return_value=httpx.Response(200, json=_gist("aaa"))
            )
            route_b = mock.get("/api/gists/bbb").mock(
                return_value=httpx.Response(200, json=_gist("bbb"))
            )
            server._get_client()
            server.get_gist("aaa", token="og_USER_A")
            server.get_gist("bbb", token="og_USER_B")
            assert (
                route_a.calls[0].request.headers["authorization"] == "Bearer og_USER_A"
            )
            assert (
                route_b.calls[0].request.headers["authorization"] == "Bearer og_USER_B"
            )

    def test_no_token_uses_env_default(self):
        with respx.mock(base_url="https://paste.test.local") as mock:
            route = mock.get("/api/gists/abc").mock(
                return_value=httpx.Response(200, json=_gist("abc"))
            )
            server._get_client()
            server.get_gist("abc")
            assert (
                route.calls[0].request.headers["authorization"] == "Bearer og_testtoken"
            )


# ── Gist list tools ───────────────────────────────────────────────────────────


class TestListTools:
    @patch.object(server, "_get_client")
    def test_list_gists(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_gists.return_value = Page(
            items=[_gist("a"), _gist("b")], total=2, total_pages=1, has_next=False
        )
        mock_get.return_value = mock_client

        result = _parse(server.list_gists())
        assert len(result["items"]) == 2

    @patch.object(server, "_get_client")
    def test_list_gists_passes_pagination_and_token(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_gists.return_value = Page(items=[])
        mock_get.return_value = mock_client

        server.list_gists(
            page=2, per_page=50, since="2024-06-01T00:00:00Z", token="og_x"
        )
        mock_client.list_gists.assert_called_once_with(
            page=2, per_page=50, since="2024-06-01T00:00:00Z", token="og_x"
        )


# ── Single gist tools ─────────────────────────────────────────────────────────


class TestSingleGistTools:
    @patch.object(server, "_get_client")
    def test_get_gist(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        result = _parse(server.get_gist("abc"))
        assert result["id"] == "abc"
        mock_client.get_gist.assert_called_once_with("abc", token=None)

    @patch.object(server, "_get_client")
    def test_create_gist_converts_files_format(self, mock_get):
        mock_client = MagicMock()
        mock_client.create_gist.return_value = _gist("new")
        mock_get.return_value = mock_client

        server.create_gist(files={"readme.md": "# Hello"}, title="Test")
        mock_client.create_gist.assert_called_once_with(
            title="Test",
            description=None,
            files={"readme.md": {"content": "# Hello"}},
            visibility="public",
            topics=None,
            expire=None,
            token=None,
        )

    @patch.object(server, "_get_client")
    def test_update_gist_converts_files_format(self, mock_get):
        mock_client = MagicMock()
        mock_client.update_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        server.update_gist("abc", files={"readme.md": "new content"})
        mock_client.update_gist.assert_called_once_with(
            "abc",
            title=None,
            description=None,
            visibility=None,
            files={"readme.md": {"content": "new content"}},
            token=None,
        )

    @patch.object(server, "_get_client")
    def test_update_gist_delete_file_via_null(self, mock_get):
        mock_client = MagicMock()
        mock_client.update_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        server.update_gist("abc", files={"old.txt": None})
        mock_client.update_gist.assert_called_once_with(
            "abc",
            title=None,
            description=None,
            visibility=None,
            files={"old.txt": None},
            token=None,
        )

    @patch.object(server, "_get_client")
    def test_delete_gist(self, mock_get):
        mock_client = MagicMock()
        mock_client.delete_gist.return_value = True
        mock_get.return_value = mock_client

        result = _parse(server.delete_gist("abc"))
        assert result["ok"] is True
        mock_client.delete_gist.assert_called_once_with("abc", token=None)


# ── Error propagation ─────────────────────────────────────────────────────────


class TestErrorPropagation:
    @patch.object(server, "_get_client")
    def test_api_error_returns_error_json(self, mock_get):
        mock_get.side_effect = OpengistError(404, "Gist not found")

        result = _parse(server.get_gist("missing"))
        assert result["ok"] is False
        assert result["status"] == 404

    @patch.object(server, "_get_client")
    def test_error_on_create_gist(self, mock_get):
        mock_get.side_effect = OpengistError(401, "Unauthorized")

        result = _parse(server.create_gist(files={"f.txt": "content"}))
        assert result["ok"] is False
        assert result["status"] == 401
