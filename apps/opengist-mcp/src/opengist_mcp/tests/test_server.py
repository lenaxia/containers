"""Tests for the MCP server tool layer.

These test the server.py wrapper — tool functions that call the client,
serialize results to JSON strings, and handle errors. The client itself is
mocked so we isolate the wrapping logic.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Import server module after setting env
os.environ.setdefault("OPENGIST_URL", "https://paste.test.local")
os.environ.setdefault("OPENGIST_TOKEN", "og_testtoken")

from opengist_mcp import server
from opengist_mcp.client import OpengistError, Page


def _parse(result: str) -> dict:
    """All tools return JSON strings — parse for assertions."""
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
        assert result["opengist_url"] == "https://paste.test.local"
        assert result["has_default_token"] is True


# ── Env var resolution ────────────────────────────────────────────────────────


class TestEnvResolution:
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
        client = server._get_client()
        assert client._timeout == 60

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_url_raises(self):
        with pytest.raises(OpengistError, match="OPENGIST_URL"):
            server._get_client()


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
        assert result["total"] == 2
        assert result["has_next"] is False

    @patch.object(server, "_get_client")
    def test_list_public_gists(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_public_gists.return_value = Page(items=[_gist("pub")])
        mock_get.return_value = mock_client

        result = _parse(server.list_public_gists())
        assert len(result["items"]) == 1

    @patch.object(server, "_get_client")
    def test_list_forked_gists(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_forked_gists.return_value = Page(items=[_gist("fork1")])
        mock_get.return_value = mock_client

        result = _parse(server.list_forked_gists())
        assert len(result["items"]) == 1

    @patch.object(server, "_get_client")
    def test_list_gists_passes_pagination_params(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_gists.return_value = Page(items=[])
        mock_get.return_value = mock_client

        server.list_gists(page=2, per_page=50, since="2024-06-01T00:00:00Z")
        mock_client.list_gists.assert_called_once_with(
            page=2, per_page=50, since="2024-06-01T00:00:00Z"
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
        mock_client.get_gist.assert_called_once_with("abc")

    @patch.object(server, "_get_client")
    def test_create_gist_converts_files_format(self, mock_get):
        """The tool takes dict[str, str] but client expects dict[str, dict]."""
        mock_client = MagicMock()
        mock_client.create_gist.return_value = _gist("new")
        mock_get.return_value = mock_client

        server.create_gist(
            files={"readme.md": "# Hello"},
            title="Test",
            visibility="unlisted",
        )
        mock_client.create_gist.assert_called_once_with(
            title="Test",
            description=None,
            files={"readme.md": {"content": "# Hello"}},
            visibility="unlisted",
            topics=None,
        )

    @patch.object(server, "_get_client")
    def test_create_gist_with_topics(self, mock_get):
        mock_client = MagicMock()
        mock_client.create_gist.return_value = _gist("new")
        mock_get.return_value = mock_client

        server.create_gist(
            files={"f.txt": "content"},
            topics=["runbook", "incident"],
        )
        call_kwargs = mock_client.create_gist.call_args.kwargs
        assert call_kwargs["topics"] == ["runbook", "incident"]

    @patch.object(server, "_get_client")
    def test_update_gist(self, mock_get):
        mock_client = MagicMock()
        mock_client.update_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        server.update_gist("abc", title="New Title")
        mock_client.update_gist.assert_called_once_with(
            "abc", title="New Title", description=None, visibility=None, files=None
        )

    @patch.object(server, "_get_client")
    def test_delete_gist(self, mock_get):
        mock_client = MagicMock()
        mock_client.delete_gist.return_value = True
        mock_get.return_value = mock_client

        result = _parse(server.delete_gist("abc"))
        assert result["ok"] is True
        mock_client.delete_gist.assert_called_once_with("abc")


# ── Fork ──────────────────────────────────────────────────────────────────────


class TestForkTool:
    @patch.object(server, "_get_client")
    def test_fork_gist(self, mock_get):
        mock_client = MagicMock()
        mock_client.fork_gist.return_value = _gist("fork123")
        mock_get.return_value = mock_client

        result = _parse(server.fork_gist("abc"))
        assert result["id"] == "fork123"


# ── Commits & Revisions ───────────────────────────────────────────────────────


class TestCommitTools:
    @patch.object(server, "_get_client")
    def test_list_commits(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_gist_commits.return_value = Page(
            items=[{"version": "sha1"}], total=1
        )
        mock_get.return_value = mock_client

        result = _parse(server.list_gist_commits("abc"))
        assert len(result["items"]) == 1
        assert result["items"][0]["version"] == "sha1"

    @patch.object(server, "_get_client")
    def test_get_revision(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_gist_revision.return_value = _gist("abc")
        mock_get.return_value = mock_client

        result = _parse(server.get_gist_revision("abc", "sha123"))
        assert result["id"] == "abc"

    @patch.object(server, "_get_client")
    def test_get_raw_file(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_raw_file.return_value = "# Raw content"
        mock_get.return_value = mock_client

        result = server.get_raw_file("abc", "sha123", "readme.md")
        assert result == "# Raw content"

    @patch.object(server, "_get_client")
    def test_list_gist_forks(self, mock_get):
        mock_client = MagicMock()
        mock_client.list_gist_forks.return_value = Page(items=[_gist("child1")])
        mock_get.return_value = mock_client

        result = _parse(server.list_gist_forks("abc"))
        assert len(result["items"]) == 1


# ── Users ─────────────────────────────────────────────────────────────────────


class TestUserTools:
    @patch.object(server, "_get_client")
    def test_get_authenticated_user(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_authenticated_user.return_value = {
            "login": "alice",
            "email": "a@b.c",
        }
        mock_get.return_value = mock_client

        result = _parse(server.get_authenticated_user())
        assert result["login"] == "alice"

    @patch.object(server, "_get_client")
    def test_get_user(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_user.return_value = {"login": "bob"}
        mock_get.return_value = mock_client

        result = _parse(server.get_user("bob"))
        assert result["login"] == "bob"


# ── Error propagation ─────────────────────────────────────────────────────────


class TestErrorPropagation:
    @patch.object(server, "_get_client")
    def test_api_error_returns_error_json(self, mock_get):
        mock_get.side_effect = OpengistError(404, "Gist not found")

        result = _parse(server.get_gist("missing"))
        assert result["ok"] is False
        assert result["status"] == 404
        assert "Gist not found" in result["error"]

    @patch.object(server, "_get_client")
    def test_value_error_returns_error_json(self, mock_get):
        mock_get.side_effect = ValueError("bad input")

        result = _parse(server.get_gist("x"))
        assert result["ok"] is False
        assert "bad input" in result["error"]

    @patch.object(server, "_get_client")
    def test_error_on_create_gist(self, mock_get):
        mock_get.side_effect = OpengistError(401, "Unauthorized")

        result = _parse(server.create_gist(files={"f.txt": "content"}))
        assert result["ok"] is False
        assert result["status"] == 401


# ── Token passthrough ─────────────────────────────────────────────────────────


class TestTokenPassthrough:
    @patch.object(server, "_get_client")
    def test_token_passed_to_get_client(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        server.get_gist("abc", token="og_custom_user")
        mock_get.assert_called_once_with("og_custom_user")

    @patch.object(server, "_get_client")
    def test_no_token_passes_none(self, mock_get):
        mock_client = MagicMock()
        mock_client.get_gist.return_value = _gist("abc")
        mock_get.return_value = mock_client

        server.get_gist("abc")
        mock_get.assert_called_once_with(None)
