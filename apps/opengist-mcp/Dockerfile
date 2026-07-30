# syntax=docker/dockerfile:1
#
# opengist-mcp — MCP server bridging LLM agents to an Opengist instance.
#
# Architecture:
#   Node supergateway (HTTP/SSE on :8000)  ←  spawns stdio child  ←
#     python -m opengist_mcp (this image)
#
# Mirrors the kicad-mcp deployment pattern in this cluster:
#   - supergateway wraps a stdio MCP server as a network endpoint
#   - LLM pods reach it via ClusterIP at http://opengist-mcp.home.svc:8000/sse
#   - No inbound auth (in-cluster only); Authelia protects upstream LiteLLM
#
# Auth model:
#   - Default: OPENGIST_TOKEN env var preloaded at startup
#   - Override: per-call ``token`` parameter on each MCP tool
#
# Multi-arch: amd64 only.

FROM docker.io/library/python:3.12-slim
ARG VERSION
ARG VENDOR

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    PYTHONPATH=/app

USER root

# ──────────────────────────────────────────────────────────────────────────────
# 1. System deps + Node.js (for supergateway)
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update
apt-get install -y --no-install-recommends \
        ca-certificates curl \
        nodejs npm
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 2. Python deps
# ──────────────────────────────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir \
        "mcp[cli]>=1.0,<2.0" \
        "httpx>=0.27,<1.0"

# ──────────────────────────────────────────────────────────────────────────────
# 3. supergateway — wraps stdio MCP servers as HTTP/SSE endpoints
# ──────────────────────────────────────────────────────────────────────────────
RUN npm install -g supergateway@3.4.3
RUN NODE_BIN=$(command -v node) \
    && NODE_GLOBAL=$(npm root -g) \
    && rm -f /usr/local/bin/supergateway \
    && printf '#!/bin/sh\nexport NODE_PATH=%s\nexec %s %s/supergateway/dist/index.js "$@"\n' \
        "$NODE_GLOBAL" "$NODE_BIN" "$NODE_GLOBAL" > /usr/local/bin/supergateway \
    && chmod +x /usr/local/bin/supergateway

# ──────────────────────────────────────────────────────────────────────────────
# 4. Application code
# ──────────────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY src/opengist_mcp ./opengist_mcp

# ──────────────────────────────────────────────────────────────────────────────
# 5. Runtime user — matches the cluster default (APP_UID=568)
# ──────────────────────────────────────────────────────────────────────────────
RUN groupadd -g 568 app && useradd -u 568 -g 568 -d /home/app -m -s /usr/sbin/nologin app \
    && install -d -o 568 -g 568 -m 0755 /home/app

USER app:app
WORKDIR /home/app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/supergateway"]
CMD [ \
    "--stdio", "python3 -m opengist_mcp", \
    "--port", "8000", \
    "--healthEndpoint", "/healthz", \
    "--logLevel", "info" \
]
