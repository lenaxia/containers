"""Tests for the Opengist API client.

These tests verify the client's contract against the Opengist OpenAPI 3.1 spec
(https://github.com/thomiceli/opengist/blob/master/docs/api.md). HTTP calls are
mocked with respx so no live instance is required.

Spec reference: each test class documents the API operation it covers.

Auth model (final design):
  - Default token preloaded via OPENGIST_TOKEN env var
  - Optional per-call ``token`` override to operate as a specific user
  - When no token is available, anonymous calls are made (public gists only)
"""

from __future__ import annotations

import httpx
import pytest
import respx

from opengist_mcp.client import OpengistClient, OpengistError


BASE = "https://paste.test.local"
TOKEN = "og_testtoken123"
OTHER_TOKEN = "og_othertoken456"


def _gist_simple(uuid="abc123", title="My Gist", visibility="public"):
    return {
        "id": uuid,
        "slug_url": f"{BASE}/user/{uuid}",
        "owner": {"id": 1, "login": "alice", "username": "alice", "type": "User"},
        "title": title,
        "html_url": f"{BASE}/user/{uuid}",
        "description": "test desc",
        "public": visibility == "public",
        "visibility": visibility,
        "like_count": 0,
        "fork_count": 0,
        "clone_url": f"{BASE}/user/{uuid}.git",
        "ssh_url": "",
        "topics": [],
        "archived": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "expires_at": None,
    }


def _gist_detail(uuid="abc123"):
    gist = _gist_simple(uuid)
    gist.update(
        {
            "fork_of": None,
            "forks": [],
            "files": {
                "readme.md": {
                    "filename": "readme.md",
                    "type": "text/plain",
                    "language": "Markdown",
                    "size": 20,
                    "truncated": False,
                    "content": "# Hello World",
                    "encoding": "utf-8",
                }
            },
            "commits": [
                {
                    "version": "abc123def456",
                    "author": {"name": "alice", "email": "alice@test.local"},
                    "user": {
                        "id": 1,
                        "login": "alice",
                        "username": "alice",
                        "type": "User",
                    },
                    "change_status": {
                        "files_changed": 1,
                        "additions": 1,
                        "deletions": 0,
                        "total": 1,
                    },
                    "committed_at": "2024-01-01T00:00:00Z",
                }
            ],
            "truncated": False,
        }
    )
    return gist


def _user(login="alice", uid=1):
    return {
        "id": uid,
        "login": login,
        "username": login,
        "avatar_url": "",
        "type": "User",
        "created_at": "2024-01-01T00:00:00Z",
    }


def _commit(version="sha123"):
    return {
        "version": version,
        "author": {"name": "alice", "email": "alice@test.local"},
        "user": {"id": 1, "login": "alice", "username": "alice", "type": "User"},
        "change_status": {
            "files_changed": 1,
            "additions": 1,
            "deletions": 0,
            "total": 1,
        },
        "committed_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def client():
    return OpengistClient(base_url=BASE, token=TOKEN)


@pytest.fixture
def anon_client(monkeypatch):
    monkeypatch.delenv("OPENGIST_TOKEN", raising=False)
    return OpengistClient(base_url=BASE)


# ── Auth resolution ────────────────────────────────────────────────────────────


class TestAuthResolution:
    """Spec: Auth uses Bearer scheme. Token from per-call param or env."""

    def test_preloaded_token_used_by_default(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/api/gists").mock(
                return_value=httpx.Response(200, json=[])
            )
            list(client.list_gists())
            req = route.calls[0].request
            assert req.headers["authorization"] == f"Bearer {TOKEN}"

    def test_per_call_token_overrides_preloaded(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/api/gists").mock(
                return_value=httpx.Response(200, json=[])
            )
            list(client.list_gists(token=OTHER_TOKEN))
            req = route.calls[0].request
            assert req.headers["authorization"] == f"Bearer {OTHER_TOKEN}"

    def test_anon_client_sends_no_auth_header(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/api/gists/public").mock(
                return_value=httpx.Response(200, json=[])
            )
            list(anon_client.list_public_gists())
            req = route.calls[0].request
            assert "authorization" not in req.headers

    def test_anon_client_per_call_token_works(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/api/gists").mock(
                return_value=httpx.Response(200, json=[])
            )
            list(anon_client.list_gists(token=TOKEN))
            req = route.calls[0].request
            assert req.headers["authorization"] == f"Bearer {TOKEN}"


# ── Gist CRUD ──────────────────────────────────────────────────────────────────


class TestListGists:
    """Spec: GET /gists — list authenticated user's gists."""

    def test_list_gists(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists").mock(
                return_value=httpx.Response(
                    200, json=[_gist_simple("a"), _gist_simple("b")]
                )
            )
            gists = list(client.list_gists())
            assert len(gists) == 2
            assert gists[0]["id"] == "a"

    def test_pagination(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists").mock(
                return_value=httpx.Response(
                    200,
                    json=[_gist_simple("a")],
                    headers={
                        "X-Page": "1",
                        "X-Per-Page": "1",
                        "X-Total": "2",
                        "X-Total-Pages": "2",
                        "Link": f'<{BASE}/api/gists?page=2&per_page=1>; rel="next"',
                    },
                )
            )
            page = client.list_gists(page=1, per_page=1)
            gists = list(page)
            assert len(gists) == 1
            assert page.total == 2
            assert page.total_pages == 2
            assert page.has_next is True

    def test_since_param(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/api/gists").mock(
                return_value=httpx.Response(200, json=[])
            )
            list(client.list_gists(since="2024-01-01T00:00:00Z"))
            req = route.calls[0].request
            assert req.url.params["since"] == "2024-01-01T00:00:00Z"


class TestListPublicGists:
    """Spec: GET /gists/public — list all public gists."""

    def test_list_public(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/public").mock(
                return_value=httpx.Response(200, json=[_gist_simple("pub")])
            )
            gists = list(anon_client.list_public_gists())
            assert len(gists) == 1


class TestGetGist:
    """Spec: GET /gists/{uuid} — get single gist with file contents."""

    def test_get_gist(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123").mock(
                return_value=httpx.Response(200, json=_gist_detail("abc123"))
            )
            gist = client.get_gist("abc123")
            assert gist["id"] == "abc123"
            assert "readme.md" in gist["files"]
            assert gist["files"]["readme.md"]["content"] == "# Hello World"

    def test_get_gist_not_found(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/nope").mock(
                return_value=httpx.Response(
                    404, json={"message": "Not found", "status": 404}
                )
            )
            with pytest.raises(OpengistError, match="404"):
                client.get_gist("nope")


class TestCreateGist:
    """Spec: POST /gists — create a gist. Requires gist:write scope."""

    def test_create_gist(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/api/gists").mock(
                return_value=httpx.Response(201, json=_gist_detail("new123"))
            )
            gist = client.create_gist(
                title="Test Gist",
                files={"readme.md": {"content": "# Hello"}},
            )
            assert gist["id"] == "new123"
            body = route.calls[0].request.read().decode()
            assert "Test Gist" in body
            assert "readme.md" in body

    def test_create_gist_private(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/api/gists").mock(
                return_value=httpx.Response(201, json=_gist_detail("priv"))
            )
            client.create_gist(
                files={"f.txt": {"content": "data"}},
                visibility="private",
            )
            body = route.calls[0].request.read().decode()
            assert '"visibility":"private"' in body.replace(" ", "")

    def test_create_gist_no_files_raises(self, client):
        with pytest.raises(ValueError, match="files"):
            client.create_gist(title="Empty", files={})


class TestUpdateGist:
    """Spec: PATCH /gists/{uuid} — update gist. Requires gist:write scope."""

    def test_update_title(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.patch("/api/gists/abc123").mock(
                return_value=httpx.Response(200, json=_gist_detail("abc123"))
            )
            client.update_gist("abc123", title="New Title")
            body = route.calls[0].request.read().decode()
            assert "New Title" in body

    def test_update_files(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.patch("/api/gists/abc123").mock(
                return_value=httpx.Response(200, json=_gist_detail("abc123"))
            )
            client.update_gist("abc123", files={"readme.md": {"content": "updated"}})
            body = route.calls[0].request.read().decode()
            assert "updated" in body

    def test_update_delete_file(self, client):
        with respx.mock(base_url=BASE) as mock:
            route = mock.patch("/api/gists/abc123").mock(
                return_value=httpx.Response(200, json=_gist_detail("abc123"))
            )
            client.update_gist("abc123", files={"old.txt": None})
            body = route.calls[0].request.read().decode()
            assert "null" in body

    def test_update_requires_at_least_one_field(self, client):
        with pytest.raises(ValueError, match="at least one"):
            client.update_gist("abc123")


class TestDeleteGist:
    """Spec: DELETE /gists/{uuid} — delete gist. Returns 204."""

    def test_delete_gist(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.delete("/api/gists/abc123").mock(return_value=httpx.Response(204))
            result = client.delete_gist("abc123")
            assert result is True

    def test_delete_gist_not_found(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.delete("/api/gists/nope").mock(
                return_value=httpx.Response(
                    404, json={"message": "Not found", "status": 404}
                )
            )
            with pytest.raises(OpengistError, match="404"):
                client.delete_gist("nope")


# ── Fork & Like ────────────────────────────────────────────────────────────────


class TestForkGist:
    """Spec: POST /gists/{uuid}/forks — fork a gist. 201 new, 200 idempotent."""

    def test_fist_new_fork(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.post("/api/gists/abc123/forks").mock(
                return_value=httpx.Response(201, json=_gist_simple("fork123"))
            )
            gist = client.fork_gist("abc123")
            assert gist["id"] == "fork123"

    def test_fork_already_forked(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.post("/api/gists/abc123/forks").mock(
                return_value=httpx.Response(200, json=_gist_simple("existingfork"))
            )
            gist = client.fork_gist("abc123")
            assert gist["id"] == "existingfork"


# ── Commits & Revisions ───────────────────────────────────────────────────────


class TestCommits:
    """Spec: GET /gists/{uuid}/commits — list commit history."""

    def test_list_commits(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123/commits").mock(
                return_value=httpx.Response(
                    200, json=[_commit("sha1"), _commit("sha2")]
                )
            )
            commits = list(client.list_gist_commits("abc123"))
            assert len(commits) == 2
            assert commits[0]["version"] == "sha1"


class TestRevisions:
    """Spec: GET /gists/{uuid}/{sha} — get gist at a revision."""

    def test_get_revision(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123/sha123").mock(
                return_value=httpx.Response(200, json=_gist_detail("abc123"))
            )
            gist = client.get_gist_revision("abc123", "sha123")
            assert gist["id"] == "abc123"


class TestRawFile:
    """Spec: GET /gists/{uuid}/files/{sha}/{filename} — raw file content."""

    def test_get_raw_file(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123/files/sha123/readme.md").mock(
                return_value=httpx.Response(200, content=b"# Hello World")
            )
            content = client.get_raw_file("abc123", "sha123", "readme.md")
            assert content == "# Hello World"


# ── Collections ────────────────────────────────────────────────────────────────


class TestCollections:
    """Spec: GET /gists/liked, /gists/forked, /gists/{uuid}/forks."""

    def test_list_forked(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/forked").mock(
                return_value=httpx.Response(200, json=[_gist_simple("forked1")])
            )
            gists = list(client.list_forked_gists())
            assert len(gists) == 1

    def test_list_gist_forks(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123/forks").mock(
                return_value=httpx.Response(200, json=[_gist_simple("child1")])
            )
            forks = list(client.list_gist_forks("abc123"))
            assert len(forks) == 1


# ── Users ──────────────────────────────────────────────────────────────────────


class TestUsers:
    """Spec: GET /user, GET /users/{username}."""

    def test_get_authenticated_user(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/user").mock(
                return_value=httpx.Response(
                    200, json={**_user(), "email": "alice@test.local"}
                )
            )
            user = client.get_authenticated_user()
            assert user["login"] == "alice"
            assert user["email"] == "alice@test.local"

    def test_get_user_by_username(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/users/bob").mock(
                return_value=httpx.Response(200, json=_user("bob", 2))
            )
            user = anon_client.get_user("bob")
            assert user["login"] == "bob"

    def test_get_user_not_found(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/users/nobody").mock(
                return_value=httpx.Response(
                    404, json={"message": "Not found", "status": 404}
                )
            )
            with pytest.raises(OpengistError, match="404"):
                anon_client.get_user("nobody")


# ── Error handling ────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Spec: Errors return {message, status} with appropriate HTTP codes."""

    def test_unauthorized_raises(self, anon_client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists").mock(
                return_value=httpx.Response(
                    401, json={"message": "Unauthorized", "status": 401}
                )
            )
            with pytest.raises(OpengistError, match="401"):
                list(anon_client.list_gists(token="og_invalid"))

    def test_forbidden_raises(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.patch("/api/gists/abc123").mock(
                return_value=httpx.Response(
                    403, json={"message": "Forbidden", "status": 403}
                )
            )
            with pytest.raises(OpengistError, match="403"):
                client.update_gist("abc123", title="hack")

    def test_validation_error_raises(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.post("/api/gists").mock(
                return_value=httpx.Response(
                    422, json={"message": "invalid visibility", "status": 422}
                )
            )
            with pytest.raises(OpengistError, match="422"):
                client.create_gist(
                    files={"f.txt": {"content": "data"}}, visibility="bogus"
                )

    def test_server_error_raises(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123").mock(
                return_value=httpx.Response(
                    500, json={"message": "Internal error", "status": 500}
                )
            )
            with pytest.raises(OpengistError, match="500"):
                client.get_gist("abc123")

    def test_error_message_in_exception(self, client):
        with respx.mock(base_url=BASE) as mock:
            mock.get("/api/gists/abc123").mock(
                return_value=httpx.Response(
                    404, json={"message": "Gist not found", "status": 404}
                )
            )
            with pytest.raises(OpengistError) as exc_info:
                client.get_gist("abc123")
            assert "Gist not found" in str(exc_info.value)
