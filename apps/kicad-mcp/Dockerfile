# syntax=docker/dockerfile:1
#
# kicad-mcp — MCP server that bridges an LLM agent to KiCad 10 projects.
#
# Architecture:
#   Node supergateway (HTTP/SSE on :8000)  ←  spawns stdio child  ←
#     python -m kicad_mcp (this image)
#
# This mirrors the hass-mcp deployment pattern in this cluster:
#   - supergateway wraps a stdio MCP server as a network endpoint
#   - LLM pods reach it via ClusterIP at http://kicad-mcp.home.svc:8000/sse
#   - No inbound auth (in-cluster only); Authelia protects upstream LiteLLM
#
# What the MCP server actually exposes:
#   - File-based operations on .kicad_pro / .kicad_sch / .kicad_pcb (via pcbnew
#     SWIG bindings, kiutils, skidl)
#   - kicad-cli wrappers: ERC, DRC, gerber/drill/step export, BOM export
#   - kibot wrappers: full fab-output pipelines defined by config.kibot.yaml
#   - Project discovery: list projects under /projects, open/inspect a project
#   - Triggering of the kicad-kibot Kubernetes Job for heavy CI runs (RBAC'd)
#
# KiCad IPC API: KiCad 10's IPC API (gRPC/NNG) has improved headless support
# over 9. The v1 MCP server remains file-based (kicad-cli + kibot) for
# portability; the kicad-python client is installed so an `ipc_*` tool set can
# connect to /tmp/kicad/api.sock (shared emptyDir with kicad-desktop) once
# the desktop pod exposes it.
#
# Multi-arch: amd64 only (Ubuntu amd64 packages).

ARG TARGETARCH
FROM docker.io/library/ubuntu:24.04
ARG VERSION
ARG VENDOR

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    # kicad_mcp is COPY'd to /app/kicad_mcp — put /app on the import path so
    # `python3 -m kicad_mcp` resolves without a pip install step.
    PYTHONPATH=/app

USER root

# ──────────────────────────────────────────────────────────────────────────────
# 1. KiCad 10.0 official PPA (ppa:kicad/kicad-10.0-releases).
#    The old apt.kicad.org was decommissioned; KiCad 10 ships via the Launchpad
#    PPA. KiCad 10's IPC API improvements are the reason we target 10 over 8/9.
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update
apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
        python3 python3-pip python3-venv \
        nodejs npm \
        git

# KiCad 10 PPA signing key + repo.
install -d -m 0755 /etc/apt/keyrings
curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xFDA854F61C4D0D9572BB95E5245D5502FAD7A805" \
    | gpg --dearmor --yes -o /etc/apt/keyrings/kicad.gpg
chmod 0644 /etc/apt/keyrings/kicad.gpg
echo "deb [signed-by=/etc/apt/keyrings/kicad.gpg] https://ppa.launchpadcontent.net/kicad/kicad-10.0-releases/ubuntu noble main" \
    > /etc/apt/sources.list.d/kicad.list

# Pre-seed debconf so apt doesn't prompt for the kicad-common fonts EULA.
echo "resconf kicad-common kicad-common/accepted_eula boolean true" | debconf-set-selections

apt-get update
apt-get install -y --no-install-recommends kicad

apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 2. Python MCP server deps + KiCad automation toolchain
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
pip3 install --break-system-packages --no-cache-dir \
        "mcp[cli]>=1.0,<2.0" \
        kibot \
        skidl \
        kiutils \
        kicad-python \
        pyyaml \
        httpx
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 3. supergateway — wraps stdio MCP servers as HTTP/SSE endpoints
#    (mirrors the hass-mcp deployment in this cluster)
# ──────────────────────────────────────────────────────────────────────────────
RUN npm install -g supergateway@3.4.3
# Build a wrapper script at a fixed path that execs node against supergateway's
# JS entry point. Using NODE_PATH so node can resolve the globally-installed
# module (avoids the symlink/circular-link issues with npm global bin).
RUN NODE_BIN=$(command -v node) \
    && NODE_GLOBAL=$(npm root -g) \
    && printf '#!/bin/sh\nexport NODE_PATH=%s\nexec %s %s/node_modules/supergateway/dist/index.js "$@"\n' \
        "$NODE_GLOBAL" "$NODE_BIN" "$NODE_GLOBAL" > /usr/local/bin/supergateway \
    && chmod +x /usr/local/bin/supergateway

# ──────────────────────────────────────────────────────────────────────────────
# 4. Application code
# ──────────────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY src/kicad_mcp ./kicad_mcp

# ──────────────────────────────────────────────────────────────────────────────
# 5. Runtime user — matches the cluster default (APP_UID=568)
# ──────────────────────────────────────────────────────────────────────────────
RUN groupadd -g 568 app && useradd -u 568 -g 568 -d /home/app -m -s /usr/sbin/nologin app \
    && install -d -o 568 -g 568 -m 0755 /home/app /projects /config

USER app:app
WORKDIR /home/app

EXPOSE 8000

# supergateway on :8000 (SSE + health), spawns `python3 -m kicad_mcp` as the
# stdio child. The kicad_mcp module reads PROJECTS_DIR=/projects to discover
# projects. All tools are read/list/exec — no auth, in-cluster only.
ENTRYPOINT ["/usr/local/bin/supergateway"]
CMD [ \
    "--stdio", "python3 -m kicad_mcp", \
    "--port", "8000", \
    "--healthEndpoint", "/healthz", \
    "--logLevel", "info" \
]
