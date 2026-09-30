# syntax=docker/dockerfile:1

FROM docker.io/library/python:3.12-slim-bookworm
ARG VERSION

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER root
WORKDIR /opt/ai4trade

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        catatonit \
        tzdata \
    && mkdir -p /workspace/ai4trade \
    && chmod 1777 /workspace/ai4trade \
    && rm -rf /var/lib/apt/lists/* /tmp/*

COPY . /opt/ai4trade/

USER nobody:nogroup
WORKDIR /workspace/ai4trade

ENTRYPOINT ["/usr/bin/catatonit", "--", "/opt/ai4trade/entrypoint.sh"]
