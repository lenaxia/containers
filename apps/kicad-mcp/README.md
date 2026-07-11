# kicad-mcp

MCP (Model Context Protocol) server bridging LLM agents to KiCad 9.

Built and used by the [talos-ops-prod](https://github.com/lenaxia/talos-ops-prod)
cluster — see `docs/kicad-streaming-workstation.md` in that repo for the full
deployment guide.

## What it does

Wraps `kicad-cli` + `kibot` + `pcbnew` Python bindings as MCP tools. Deployed
in-cluster alongside the `kicad-desktop` pod; reached by LLM pods via
ClusterIP:

```
http://kicad-mcp.home.svc.cluster.local:8000/sse
```

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ Pod: kicad-mcp-XXXX (Deployment, replicas=1)                   │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Container: main                                            │ │
│ │  supergateway (Node, HTTP/SSE on :8000)                    │ │
│ │     └── stdio child: python3 -m kicad_mcp                  │ │
│ └────────────────────────────────────────────────────────────┘ │
│ PVCs: /projects (RWX, Longhorn), /config (RWO, Longhorn)       │
└────────────────────────────────────────────────────────────────┘
                            ▲
                            │ in-cluster HTTP/SSE
                            │
              ┌─────────────┴────────────┐
              │  LiteLLM / Open-WebUI    │
              │  (existing LLM pods)     │
              └──────────────────────────┘
```

## MCP tools

See [`server.py`](src/kicad_mcp/server.py). Summary:

- **`list_kicad_projects`** — discover projects under `/projects`
- **`open_project`** — resolve a project path to its files
- **`list_kibot_configs`** — list `*.kibot.yaml` files in a project
- **`run_electrical_rules_check`** — ERC via `kicad-cli sch erc`
- **`run_design_rules_check`** — DRC via `kicad-cli pcb drc`
- **`export_gerber_files`** — Gerbers via `kicad-cli pcb export gerbers`
- **`export_drill_files`** — Excellon / Gerber drill
- **`export_step_model`** — STEP 3D model
- **`run_kibot_pipeline`** — run a full kibot config (e.g. JLCPCB fab bundle)
- **`health`** — sanity probe

## Why not KiCad IPC API?

KiCad 9's IPC API is PCB-editor-only and **requires the GUI running** —
there's no headless mode until KiCad 11 ships. This server is intentionally
file-based so it works in a headless pod (no X server needed in this image).

When KiCad 11 lands, this server gains an optional `ipc_*` tool set that
connects to `/tmp/kicad/api.sock` (shared emptyDir with the kicad-desktop pod)
for live in-process board manipulation.

## Local dev

```bash
# Build
docker buildx bake image-local

# Run standalone (stdio MCP, no supergateway)
docker run --rm -it \
    -v /path/to/projects:/projects:rw \
    ghcr.io/lenaxia/kicad-mcp:0.1.0 \
    python3 -m kicad_mcp

# Run with supergateway (HTTP/SSE on :8000)
docker run --rm -p 8000:8000 \
    -v /path/to/projects:/projects:rw \
    ghcr.io/lenaxia/kicad-mcp:0.1.0

# Probe
curl http://localhost:8000/healthz
```
