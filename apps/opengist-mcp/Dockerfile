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

FROM docker.io/library/python:3.13-alpine3.21
ARG VERSION
ARG VENDOR

ENV TZ=UTC \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    PYTHONPATH=/app

USER root

RUN <<'EOF'
set -eux
apk add --no-cache \
        ca-certificates \
        nodejs \
        npm
EOF

RUN pip3 install --no-cache-dir \
        "mcp[cli]>=1.0,<2.0" \
        "httpx>=0.27,<1.0"

RUN npm install -g supergateway@3.4.3
RUN NODE_BIN=$(command -v node) \
    && NODE_GLOBAL=$(npm root -g) \
    && rm -f /usr/local/bin/supergateway \
    && printf '#!/bin/sh\nexport NODE_PATH=%s\nexec %s %s/supergateway/dist/index.js "$@"\n' \
        "$NODE_GLOBAL" "$NODE_BIN" "$NODE_GLOBAL" > /usr/local/bin/supergateway \
    && chmod +x /usr/local/bin/supergateway

WORKDIR /app
COPY src/opengist_mcp ./opengist_mcp

RUN addgroup -g 568 app && adduser -u 568 -G app -D -h /home/app -s /sbin/nologin app \
    && install -d -o 568 -g 568 -m 0755 /home/app

USER app:app
WORKDIR /home/app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/supergateway"]
CMD [ \
    "--stdio", "python3 -m opengist_mcp", \
    "--port", "8000", \
    "--transport", "streamable-http", \
    "--healthEndpoint", "/healthz", \
    "--logLevel", "info" \
]
