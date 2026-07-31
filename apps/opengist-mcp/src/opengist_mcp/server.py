"""MCP tool definitions — the surface an LLM agent can call.

Tools wrap the Opengist REST API client. All tools support an optional ``token``
parameter to override the default preloaded token, enabling per-user gist
ownership when desired.

Spec: https://github.com/thomiceli/opengist/blob/master/docs/api.md
"""

from __future__ import annotations

import atexit
import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from . import __version__
from .client import OpengistClient, OpengistError

log = logging.getLogger("opengist_mcp")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

mcp = FastMCP("opengist-mcp")

_client: OpengistClient | None = None


def _get_client(token: str | None = None) -> OpengistClient:
    """Return a singleton client.

    The per-call token (if provided) is set as a one-shot override via the
    client's default-token mechanism. This avoids creating a new httpx.Client
    (and new TCP connections) on every tool call.
    """
    global _client
    if _client is None:
        base_url = os.environ.get("OPENGIST_URL", "")
        if not base_url:
            raise OpengistError(500, "OPENGIST_URL environment variable is not set")
        default_token = os.environ.get("OPENGIST_TOKEN")
        timeout = int(os.environ.get("OPENGIST_TIMEOUT", "30"))
        _client = OpengistClient(
            base_url=base_url,
            token=default_token,
            timeout=timeout,
        )
        atexit.register(_client.close)
    saved = _client._default_token
    if token:
        _client._default_token = token
    else:
        _client._default_token = os.environ.get("OPENGIST_TOKEN")
    return _client


def _error(e: Exception) -> str:
    if isinstance(e, OpengistError):
        return json.dumps(
            {"ok": False, "error": e.message, "status": e.status}, indent=2
        )
    return json.dumps({"ok": False, "error": str(e)}, indent=2)


def _page_to_dict(page) -> dict:
    return {
        "items": page.items,
        "page": page.page,
        "per_page": page.per_page,
        "total": page.total,
        "total_pages": page.total_pages,
        "has_next": page.has_next,
        "has_prev": page.has_prev,
    }


# ── Gists: list ───────────────────────────────────────────────────────────────


@mcp.tool()
def list_gists(
    page: int = 1,
    per_page: int = 30,
    since: str | None = None,
    token: str | None = None,
) -> str:
    """List gists owned by the authenticated user.

    Args:
        page: Page number (1-based, default 1).
        per_page: Items per page (max 100, default 30).
        since: Only return gists updated at/after this RFC 3339 timestamp.
        token: Optional API token (og_xxx) to act as a specific user.
               Overrides the default OPENGIST_TOKEN.

    Returns JSON: items, page, per_page, total, total_pages, has_next, has_prev.
    """
    try:
        client = _get_client(token)
        page_result = client.list_gists(page=page, per_page=per_page, since=since)
        return json.dumps(_page_to_dict(page_result), indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def list_public_gists(
    page: int = 1,
    per_page: int = 30,
    since: str | None = None,
    token: str | None = None,
) -> str:
    """List all public gists on the instance.

    Args:
        page: Page number (default 1).
        per_page: Items per page (default 30, max 100).
        since: Only return gists updated at/after this RFC 3339 timestamp.
        token: Optional API token. Overrides the default.

    Returns JSON with pagination metadata.
    """
    try:
        client = _get_client(token)
        page_result = client.list_public_gists(
            page=page, per_page=per_page, since=since
        )
        return json.dumps(_page_to_dict(page_result), indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def list_forked_gists(
    page: int = 1, per_page: int = 30, token: str | None = None
) -> str:
    """List gists the authenticated user has forked.

    Args:
        page: Page number (default 1).
        per_page: Items per page (default 30, max 100).
        token: Optional API token. Overrides the default.

    Returns JSON with pagination metadata.
    """
    try:
        client = _get_client(token)
        page_result = client.list_forked_gists(page=page, per_page=per_page)
        return json.dumps(_page_to_dict(page_result), indent=2)
    except Exception as e:
        return _error(e)


# ── Gists: single ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_gist(uuid: str, token: str | None = None) -> str:
    """Get a single gist with file contents, commits, and forks.

    Args:
        uuid: The gist's UUID or slug URL.
        token: Optional API token. Overrides the default.

    Returns JSON: full gist including files, commits, and forks.
    """
    try:
        client = _get_client(token)
        gist = client.get_gist(uuid)
        return json.dumps(gist, indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def create_gist(
    files: dict[str, str],
    title: str | None = None,
    description: str | None = None,
    visibility: str = "public",
    topics: list[str] | None = None,
    expire: str | None = None,
    token: str | None = None,
) -> str:
    """Create a new gist.

    Args:
        files: Dict of filename → content. At least one file is required.
        title: Optional title (derived from first filename if omitted).
        description: Optional description.
        visibility: 'public' (default), 'unlisted', or 'private'.
        topics: Optional list of topic tags.
        expire: Optional expiration (e.g. '24h', '7d', '30m').
        token: Optional API token to create as a specific user.
               Overrides the default OPENGIST_TOKEN.

    Returns JSON: the created gist.
    """
    try:
        client = _get_client(token)
        api_files = {name: {"content": content} for name, content in files.items()}
        gist = client.create_gist(
            title=title,
            description=description,
            files=api_files,
            visibility=visibility,
            topics=topics,
            expire=expire,
        )
        return json.dumps(gist, indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def update_gist(
    uuid: str,
    title: str | None = None,
    description: str | None = None,
    visibility: str | None = None,
    files: dict[str, str | None] | None = None,
    token: str | None = None,
) -> str:
    """Update a gist's title, description, visibility, or files.

    Args:
        uuid: The gist's UUID.
        title: New title (optional).
        description: New description (optional).
        visibility: 'public', 'unlisted', or 'private' (optional).
        files: Dict of filename → content string to update/add, or
               filename → null to delete. At least one field must be set.
        token: Optional API token. Overrides the default.

    Returns JSON: the updated gist.
    """
    try:
        client = _get_client(token)
        api_files: dict | None = None
        if files is not None:
            api_files = {}
            for name, content in files.items():
                api_files[name] = {"content": content} if content is not None else None
        gist = client.update_gist(
            uuid,
            title=title,
            description=description,
            visibility=visibility,
            files=api_files,
        )
        return json.dumps(gist, indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def delete_gist(uuid: str, token: str | None = None) -> str:
    """Delete a gist owned by the authenticated user.

    Args:
        uuid: The gist's UUID.
        token: Optional API token. Overrides the default.

    Returns JSON: {"ok": true} on success.
    """
    try:
        client = _get_client(token)
        client.delete_gist(uuid)
        return json.dumps({"ok": True}, indent=2)
    except Exception as e:
        return _error(e)


# ── Fork ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def fork_gist(uuid: str, token: str | None = None) -> str:
    """Fork a gist. Idempotent — returns existing fork if already forked.

    Args:
        uuid: The gist's UUID.
        token: Optional API token. Overrides the default.

    Returns JSON: the forked gist (new or existing).
    """
    try:
        client = _get_client(token)
        gist = client.fork_gist(uuid)
        return json.dumps(gist, indent=2)
    except Exception as e:
        return _error(e)


# ── Commits & Revisions ───────────────────────────────────────────────────────


@mcp.tool()
def list_gist_commits(
    uuid: str, page: int = 1, per_page: int = 30, token: str | None = None
) -> str:
    """List a gist's commit history (most recent first).

    Args:
        uuid: The gist's UUID.
        page: Page number (default 1).
        per_page: Items per page (default 30, max 100).
        token: Optional API token. Overrides the default.

    Returns JSON with pagination metadata.
    """
    try:
        client = _get_client(token)
        page_result = client.list_gist_commits(uuid, page=page, per_page=per_page)
        return json.dumps(_page_to_dict(page_result), indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def get_gist_revision(uuid: str, sha: str, token: str | None = None) -> str:
    """Get a gist as it stood at a specific commit SHA.

    Args:
        uuid: The gist's UUID.
        sha: Full or partial commit SHA (4–40 hex chars).
        token: Optional API token. Overrides the default.

    Returns JSON: the gist at the requested revision.
    """
    try:
        client = _get_client(token)
        gist = client.get_gist_revision(uuid, sha)
        return json.dumps(gist, indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def get_raw_file(uuid: str, sha: str, filename: str, token: str | None = None) -> str:
    """Get raw file content from a gist at a specific revision.

    Args:
        uuid: The gist's UUID.
        sha: Full or partial commit SHA (4–40 hex chars).
        filename: Name of the file within the gist.
        token: Optional API token. Overrides the default.

    Returns the raw file content as a string.
    """
    try:
        client = _get_client(token)
        content = client.get_raw_file(uuid, sha, filename)
        return content
    except Exception as e:
        return _error(e)


@mcp.tool()
def list_gist_forks(
    uuid: str, page: int = 1, per_page: int = 30, token: str | None = None
) -> str:
    """List forks of a specific gist.

    Args:
        uuid: The gist's UUID.
        page: Page number (default 1).
        per_page: Items per page (default 30, max 100).
        token: Optional API token. Overrides the default.

    Returns JSON with pagination metadata.
    """
    try:
        client = _get_client(token)
        page_result = client.list_gist_forks(uuid, page=page, per_page=per_page)
        return json.dumps(_page_to_dict(page_result), indent=2)
    except Exception as e:
        return _error(e)


# ── Users ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_authenticated_user(token: str | None = None) -> str:
    """Get the authenticated user's profile (requires user:read scope).

    Args:
        token: Optional API token. Overrides the default.

    Returns JSON: the user's profile including email.
    """
    try:
        client = _get_client(token)
        user = client.get_authenticated_user()
        return json.dumps(user, indent=2)
    except Exception as e:
        return _error(e)


@mcp.tool()
def get_user(username: str, token: str | None = None) -> str:
    """Look up a user by username (public, no auth required).

    Args:
        username: The user's username.
        token: Optional API token. Overrides the default.

    Returns JSON: the user's public profile.
    """
    try:
        client = _get_client(token)
        user = client.get_user(username)
        return json.dumps(user, indent=2)
    except Exception as e:
        return _error(e)


# ── Health ────────────────────────────────────────────────────────────────────


@mcp.tool(description="Health / sanity probe. Returns server version + Opengist URL.")
def health() -> str:
    return json.dumps(
        {
            "ok": True,
            "version": __version__,
            "opengist_url": os.environ.get("OPENGIST_URL", ""),
            "has_default_token": bool(os.environ.get("OPENGIST_TOKEN")),
        },
        indent=2,
    )


def main() -> None:
    """Entrypoint — runs the MCP server on stdio (wrapped by supergateway)."""
    log.info("opengist-mcp %s starting", __version__)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
