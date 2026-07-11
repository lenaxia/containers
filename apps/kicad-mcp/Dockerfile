# syntax=docker/dockerfile:1
#
# kicad-mcp — MCP server that bridges an LLM agent to KiCad 9 projects.
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
# KiCad IPC API: NOT used in v1. KiCad 9's IPC API is PCB-editor-only and
# requires the GUI running. KiCad 11 (not yet released) adds headless IPC.
# When KiCad 11 ships, this server gains an optional IPC client path that
# connects to /tmp/kicad/api.sock (shared emptyDir with the kicad-desktop pod).
#
# Multi-arch: amd64 only (KiCad apt repo).

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
    XDG_CACHE_HOME=/home/app/.cache

USER root

# ──────────────────────────────────────────────────────────────────────────────
# 1. KiCad 9 apt repo (for kicad-cli + pcbnew python bindings, NO GUI)
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update
apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
        python3 python3-pip python3-venv \
        nodejs npm \
        git

install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://kicad.org/gtest.asc \
    | gpg --dearmor --yes -o /etc/apt/keyrings/kicad.gpg
chmod 0644 /etc/apt/keyrings/kicad.gpg
echo "deb [signed-by=/etc/apt/keyrings/kicad.gpg] http://apt.kicad.org kicad-9.0 main" \
    > /etc/apt/sources.list.d/kicad.list

echo "resconf kicad-common kicad-common/accepted_eula boolean true" | debconf-set-selections

apt-get update
apt-get install -y --no-install-recommends \
        kicad=9.0.* \
        kicad-libraries \
        python3-kicad-pcbnew

# Cleanup
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
ENTRYPOINT ["/usr/bin/supergateway"]
CMD [ \
    "--stdio", "python3 -m kicad_mcp", \
    "--port", "8000", \
    "--healthEndpoint", "/healthz", \
    "--logLevel", "info" \
]
