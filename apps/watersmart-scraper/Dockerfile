# syntax=docker/dockerfile:1

FROM docker.io/library/python:3.13-slim-bookworm
ARG VERSION

ENV \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=true \
    UV_SYSTEM_PYTHON=true

USER root
WORKDIR /app

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        catatonit \
        curl \
        tzdata \
    && pip install uv \
    && uv pip install \
        "requests==2.31.0" \
        "paho-mqtt==2.0.0" \
        "python-dotenv==1.0.1" \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* /tmp/*

COPY . /

USER nobody:nogroup
WORKDIR /app

EXPOSE 8080

ENTRYPOINT ["/usr/bin/catatonit", "--", "/entrypoint.sh"]
