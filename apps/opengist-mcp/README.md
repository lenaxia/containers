# opengist-mcp

MCP (Model Context Protocol) server bridging LLM agents to an
[Opengist](https://github.com/thomiceli/opengist) instance.

Exposes gist CRUD, fork/like, commit history, raw file access, and user lookup
as MCP tools. Deployed in-cluster alongside LLM pods; reached via ClusterIP
through supergateway (HTTP/SSE).

## What it does

Wraps the [Opengist REST API](https://github.com/thomiceli/opengist/blob/master/docs/api.md)
as MCP tools so an LLM agent can create, read, update, delete, fork, and like
gists programmatically. Based on the OpenAPI 3.1 spec served at
`GET /api/openapi.yaml`.

## Authentication

Two modes, resolved per tool call:

1. **Default (env var)**: Set `OPENGIST_TOKEN=og_xxx` at container startup.
   All tools use this token by default. Best for a dedicated service account.

2. **Per-call override**: Every tool accepts an optional `token` parameter
   (`og_xxx`). If provided, it overrides the default for that call. Best when
   the agent needs to create gists owned by a specific user (so that user can
   edit/delete them through the web UI).

If neither is set, anonymous calls are made (public gists only). Tools requiring
authentication will return a clear error.

> The MCP server does NOT use Bearer auth for its own transport — that scheme is
> reserved for the upstream Opengist API.

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `OPENGIST_URL` | yes | — | Base URL of the Opengist instance (e.g. `https://paste.example.com`) |
| `OPENGIST_TOKEN` | no | — | Preloaded API token (`og_xxx`). |
| `OPENGIST_TIMEOUT` | no | `30` | HTTP timeout in seconds. |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Pod: opengist-mcp-XXXX (Deployment, replicas=1)              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Container: main                                          │ │
│ │  supergateway (Node, HTTP/SSE on :8000)                  │ │
│ │     └── stdio child: python3 -m opengist_mcp             │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │ in-cluster HTTP/SSE
                            │
              ┌─────────────┴────────────┐
              │  LiteLLM / Open-WebUI    │
              │  (existing LLM pods)     │
              └──────────────────────────┘
```

## MCP tools

See [`server.py`](src/opengist_mcp/server.py). Summary:

### Gists
- **`list_gists`** — list the authenticated user's gists
- **`list_public_gists`** — list all public gists on the instance
- **`get_gist`** — get a single gist with file contents
- **`create_gist`** — create a new gist
- **`update_gist`** — update a gist's title, description, visibility, or files
- **`delete_gist`** — delete a gist
- **`fork_gist`** — fork a gist

### Commits & revisions
- **`list_gist_commits`** — list a gist's commit history
- **`get_gist_revision`** — get a gist at a specific commit SHA
- **`get_gist_raw_file`** — get raw file content at a specific revision

### Collections
- **`list_forked_gists`** — list gists the caller has forked
- **`list_gist_forks`** — list forks of a specific gist

### Users
- **`get_authenticated_user`** — get the current user's profile
- **`get_user`** — look up a user by username

### Meta
- **`health`** — sanity probe

## Local dev

```bash
# Install dev deps
pip install -e src/[opengist_mcp]

# Run tests
pytest src/opengist_mcp/tests/

# Run standalone (stdio MCP)
OPENGIST_URL=https://paste.example.com \
OPENGIST_TOKEN=og_xxx \
python3 -m opengist_mcp

# Run with supergateway (HTTP/SSE on :8000)
docker run --rm -p 8000:8000 \
    -e OPENGIST_URL=https://paste.example.com \
    -e OPENGIST_TOKEN=og_xxx \
    ghcr.io/lenaxia/opengist-mcp:0.1.0

# Probe
curl http://localhost:8000/healthz
```
