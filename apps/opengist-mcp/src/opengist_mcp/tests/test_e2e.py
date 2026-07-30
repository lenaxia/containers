"""E2E tests against a real Opengist instance.

These tests create, read, update, and delete real gists — skip with
``-k "not e2e"`` if no instance is available.

Requires env vars:
  OPENGIST_E2E_URL   — base URL (e.g. https://paste.thekao.cloud)
  OPENGIST_E2E_TOKEN — API token with gist:write + user:read scopes
"""

from __future__ import annotations

import json
import os
import time
import uuid

import pytest

from opengist_mcp.client import OpengistClient, OpengistError


E2E_URL = os.environ.get("OPENGIST_E2E_URL")
E2E_TOKEN = os.environ.get("OPENGIST_E2E_TOKEN")

pytestmark = pytest.mark.skipif(
    not E2E_URL or not E2E_TOKEN,
    reason="Set OPENGIST_E2E_URL and OPENGIST_E2E_TOKEN to run E2E tests",
)


@pytest.fixture
def client():
    return OpengistClient(base_url=E2E_URL, token=E2E_TOKEN)


@pytest.fixture
def created_gist(client):
    """Create a gist for the test, delete it after."""
    uid = uuid.uuid4().hex[:12]
    gist = client.create_gist(
        title=f"e2e-test-{uid}",
        files={
            f"test-{uid}.md": {
                "content": f"# E2E Test {uid}\n\nCreated by opengist-mcp e2e suite."
            }
        },
        visibility="unlisted",
    )
    yield gist
    try:
        client.delete_gist(gist["id"])
    except Exception:
        pass


@pytest.fixture
def created_gist_two_files(client):
    """Create a gist with 2 files for the test, delete it after."""
    uid = uuid.uuid4().hex[:12]
    gist = client.create_gist(
        title=f"e2e-test-{uid}",
        files={
            f"test-{uid}.md": {
                "content": f"# E2E Test {uid}\n\nCreated by opengist-mcp e2e suite."
            },
            f"extra-{uid}.txt": {"content": "extra file to delete"},
        },
        visibility="unlisted",
    )
    yield gist
    try:
        client.delete_gist(gist["id"])
    except Exception:
        pass


class TestE2EHealth:
    def test_instance_is_up(self, client):
        user = client.get_authenticated_user()
        assert "login" in user


class TestE2EGistCRUD:
    def test_create_and_get(self, client, created_gist):
        gist = client.get_gist(created_gist["id"])
        assert gist["id"] == created_gist["id"]
        assert gist["title"].startswith("e2e-test-")
        files = list(gist["files"].values())
        assert len(files) == 1
        assert "E2E Test" in files[0]["content"]

    def test_list_gists_includes_created(self, client, created_gist):
        page = client.list_gists(per_page=100)
        ids = [g["id"] for g in page]
        assert created_gist["id"] in ids

    def test_update_gist_title(self, client, created_gist):
        updated = client.update_gist(created_gist["id"], title="e2e-updated-title")
        assert updated["title"] == "e2e-updated-title"

    def test_update_gist_add_file(self, client, created_gist):
        client.update_gist(
            created_gist["id"],
            files={"added.txt": {"content": "new file"}},
        )
        gist = client.get_gist(created_gist["id"])
        assert "added.txt" in gist["files"]

    def test_update_gist_delete_file(self, client, created_gist_two_files):
        # Opengist requires at least 1 file — use the 2-file fixture
        original_files = list(
            client.get_gist(created_gist_two_files["id"])["files"].keys()
        )
        filename = original_files[0]
        client.update_gist(created_gist_two_files["id"], files={filename: None})
        gist = client.get_gist(created_gist_two_files["id"])
        assert filename not in gist["files"]
        assert len(gist["files"]) == 1

    def test_delete_gist(self, client):
        uid = uuid.uuid4().hex[:12]
        gist = client.create_gist(
            title=f"e2e-delete-{uid}",
            files={f"del-{uid}.txt": {"content": "delete me"}},
            visibility="unlisted",
        )
        assert client.delete_gist(gist["id"]) is True
        with pytest.raises(OpengistError, match="404"):
            client.get_gist(gist["id"])


class TestE2EGistMetadata:
    def test_list_commits(self, client, created_gist):
        page = client.list_gist_commits(created_gist["id"])
        assert len(page.items) >= 1
        assert "version" in page.items[0]

    def test_list_public_gists(self, client):
        page = client.list_public_gists(per_page=5)
        assert isinstance(page.items, list)


class TestE2EFork:
    def test_fork_own_gist_rejected(self, client, created_gist):
        """Spec: forking your own gist returns 422."""
        with pytest.raises(OpengistError, match="422"):
            client.fork_gist(created_gist["id"])

    def test_list_forked_gists(self, client):
        page = client.list_forked_gists(per_page=5)
        assert isinstance(page.items, list)


class TestE2ERawFile:
    def test_get_raw_file(self, client, created_gist):
        commits = list(client.list_gist_commits(created_gist["id"]))
        sha = commits[0]["version"]
        filename = (
            list(created_gist["files"].keys())[0] if "files" in created_gist else None
        )
        if not filename:
            gist = client.get_gist(created_gist["id"])
            filename = list(gist["files"].keys())[0]
        content = client.get_raw_file(created_gist["id"], sha, filename)
        assert "E2E Test" in content


class TestE2ETokenOverride:
    def test_per_call_token_works(self, client, created_gist):
        gist = client.get_gist(created_gist["id"], token=E2E_TOKEN)
        assert gist["id"] == created_gist["id"]
