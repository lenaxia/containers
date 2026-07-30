"""Opengist API client — thin wrapper over the Opengist REST API.

Implements the endpoints defined in the OpenAPI 3.1 spec:
https://github.com/thomiceli/opengist/blob/master/docs/api.md

Auth model:
  - Default token (from OPENGIST_TOKEN) used for all calls.
  - Optional per-call ``token`` override to act as a specific user.
  - No token → anonymous (public gists only, write operations fail).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


class OpengistError(Exception):
    """Raised for any non-2xx API response. Includes status code + message."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


@dataclass
class Page:
    """Paginated result wrapper. Iterable over items; exposes pagination metadata."""

    items: list[dict]
    page: int = 1
    per_page: int = 30
    total: int | None = None
    total_pages: int | None = None
    has_next: bool = False
    has_prev: bool = False

    def __iter__(self):
        return iter(self.items)


def _parse_pagination(response: httpx.Response) -> dict[str, Any]:
    """Extract X-* pagination headers (spec: pagination via headers)."""
    h = response.headers
    total = h.get("X-Total")
    total_pages = h.get("X-Total-Pages")
    link = h.get("Link", "")
    return {
        "page": int(h.get("X-Page", "1")),
        "per_page": int(h.get("X-Per-Page", "30")),
        "total": int(total) if total else None,
        "total_pages": int(total_pages) if total_pages else None,
        "has_next": 'rel="next"' in link,
        "has_prev": 'rel="prev"' in link,
    }


class OpengistClient:
    """Opengist REST API client.

    Args:
        base_url: Opengist instance URL (e.g. https://paste.example.com).
        token: Default API token (og_xxx). Can be overridden per-call.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: int = 30,
    ):
        self._base_url = base_url.rstrip("/")
        self._default_token = token or os.environ.get("OPENGIST_TOKEN")
        self._timeout = timeout

    def _headers(self, token: str | None) -> dict[str, str]:
        t = token or self._default_token
        h: dict[str, str] = {"Accept": "application/json"}
        if t:
            h["Authorization"] = f"Bearer {t}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}/api{path}"
        resp = httpx.request(
            method,
            url,
            headers=self._headers(token),
            params=params,
            json=json,
            timeout=self._timeout,
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message", resp.text)
            except Exception:
                msg = resp.text
            raise OpengistError(resp.status_code, msg)
        return resp

    # ── Gists: list ───────────────────────────────────────────────────────────

    def list_gists(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        since: str | None = None,
        token: str | None = None,
    ) -> Page:
        """GET /gists — list the authenticated user's gists."""
        params: dict = {"page": page, "per_page": per_page}
        if since:
            params["since"] = since
        resp = self._request("GET", "/gists", token=token, params=params)
        meta = _parse_pagination(resp)
        return Page(items=resp.json(), **meta)

    def list_public_gists(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        since: str | None = None,
        token: str | None = None,
    ) -> Page:
        """GET /gists/public — list all public gists."""
        params: dict = {"page": page, "per_page": per_page}
        if since:
            params["since"] = since
        resp = self._request("GET", "/gists/public", token=token, params=params)
        meta = _parse_pagination(resp)
        return Page(items=resp.json(), **meta)

    def list_forked_gists(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        since: str | None = None,
        token: str | None = None,
    ) -> Page:
        """GET /gists/forked — list gists the caller has forked."""
        params: dict = {"page": page, "per_page": per_page}
        if since:
            params["since"] = since
        resp = self._request("GET", "/gists/forked", token=token, params=params)
        meta = _parse_pagination(resp)
        return Page(items=resp.json(), **meta)

    # ── Gists: single ─────────────────────────────────────────────────────────

    def get_gist(self, uuid: str, *, token: str | None = None) -> dict:
        """GET /gists/{uuid} — get a gist with file contents."""
        resp = self._request("GET", f"/gists/{uuid}", token=token)
        return resp.json()

    def create_gist(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        files: dict[str, dict] | None = None,
        visibility: str = "public",
        topics: list[str] | None = None,
        expire: str | None = None,
        token: str | None = None,
    ) -> dict:
        """POST /gists — create a gist. Requires gist:write scope."""
        if not files or not any(f.get("content") for f in files.values()):
            raise ValueError("files must contain at least one entry with content")
        body: dict = {"files": files, "visibility": visibility}
        if title:
            body["title"] = title
        if description:
            body["description"] = description
        if topics:
            body["topics"] = topics
        if expire:
            body["expire"] = expire
        resp = self._request("POST", "/gists", token=token, json=body)
        return resp.json()

    def update_gist(
        self,
        uuid: str,
        *,
        title: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        files: dict | None = None,
        token: str | None = None,
    ) -> dict:
        """PATCH /gists/{uuid} — update a gist. Requires gist:write scope."""
        body: dict = {}
        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description
        if visibility is not None:
            body["visibility"] = visibility
        if files is not None:
            body["files"] = files
        if not body:
            raise ValueError(
                "at least one of title, description, visibility, or files must be set"
            )
        resp = self._request("PATCH", f"/gists/{uuid}", token=token, json=body)
        return resp.json()

    def delete_gist(self, uuid: str, *, token: str | None = None) -> bool:
        """DELETE /gists/{uuid} — delete a gist. Returns True on 204."""
        self._request("DELETE", f"/gists/{uuid}", token=token)
        return True

    # ── Fork & Like ───────────────────────────────────────────────────────────

    def fork_gist(self, uuid: str, *, token: str | None = None) -> dict:
        """POST /gists/{uuid}/forks — fork a gist. 201 new, 200 idempotent."""
        resp = self._request("POST", f"/gists/{uuid}/forks", token=token)
        return resp.json()

    # ── Commits & Revisions ───────────────────────────────────────────────────

    def list_gist_commits(
        self,
        uuid: str,
        *,
        page: int = 1,
        per_page: int = 30,
        token: str | None = None,
    ) -> Page:
        """GET /gists/{uuid}/commits — list commit history."""
        params = {"page": page, "per_page": per_page}
        resp = self._request(
            "GET", f"/gists/{uuid}/commits", token=token, params=params
        )
        meta = _parse_pagination(resp)
        return Page(items=resp.json(), **meta)

    def get_gist_revision(
        self, uuid: str, sha: str, *, token: str | None = None
    ) -> dict:
        """GET /gists/{uuid}/{sha} — get a gist at a specific revision."""
        resp = self._request("GET", f"/gists/{uuid}/{sha}", token=token)
        return resp.json()

    def get_raw_file(
        self,
        uuid: str,
        sha: str,
        filename: str,
        *,
        token: str | None = None,
    ) -> str:
        """GET /gists/{uuid}/files/{sha}/{filename} — raw file content."""
        resp = self._request(
            "GET", f"/gists/{uuid}/files/{sha}/{filename}", token=token
        )
        return resp.text

    def list_gist_forks(
        self,
        uuid: str,
        *,
        page: int = 1,
        per_page: int = 30,
        token: str | None = None,
    ) -> Page:
        """GET /gists/{uuid}/forks — list forks of a gist."""
        params = {"page": page, "per_page": per_page}
        resp = self._request("GET", f"/gists/{uuid}/forks", token=token, params=params)
        meta = _parse_pagination(resp)
        return Page(items=resp.json(), **meta)

    # ── Users ─────────────────────────────────────────────────────────────────

    def get_authenticated_user(self, *, token: str | None = None) -> dict:
        """GET /user — get the authenticated user's profile. Requires user:read scope."""
        resp = self._request("GET", "/user", token=token)
        return resp.json()

    def get_user(self, username: str, *, token: str | None = None) -> dict:
        """GET /users/{username} — public user lookup."""
        resp = self._request("GET", f"/users/{username}", token=token)
        return resp.json()
