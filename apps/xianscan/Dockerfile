# syntax=docker/dockerfile:1
#
# xianscan — local-first comic/manga translation studio (Rust + ONNX Runtime).
# Upstream ships a self-contained linux-amd64 binary with the ONNX models,
# SvelteKit web UI, and Node.js runtime embedded; it runs CPU-first and
# activates CUDA only when cuDNN 9 libraries are importable at runtime.
#
# The release tarball also carries libonnxruntime_providers_*.so (CUDA/TensorRT
# execution providers). They are inert without cuDNN and an NVIDIA device, so
# the same image serves CPU and GPU hosts (NVIDIA Container Toolkit required
# for the latter, plus cuDNN 9 on LD_LIBRARY_PATH).

FROM docker.io/library/ubuntu:24.04
ARG VERSION

ENV DEBIAN_FRONTEND=noninteractive \
    XDG_DATA_HOME=/config \
    XDG_CACHE_HOME=/config/.cache \
    HOME=/config

USER root
WORKDIR /app

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fontconfig \
        fonts-dejavu-core \
        wget \
    && wget -q "https://github.com/ArbenApura/xianscan-rust/releases/download/v${VERSION}/xianscan-linux-x86_64.tar.gz" -O /tmp/xianscan.tar.gz \
    && tar -xzf /tmp/xianscan.tar.gz -C /app \
    && rm -rf /tmp/xianscan.tar.gz \
    && chmod +x /app/xianscan \
    && apt-get purge -y wget \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 568 app \
    && useradd -u 568 -g 568 -d /config -M -s /usr/sbin/nologin app \
    && mkdir -p /config \
    && chown -R app:app /config \
    && chown -R root:root /app \
    && chmod -R 755 /app

USER app:app

VOLUME ["/config"]

EXPOSE 8124

ENTRYPOINT ["/app/xianscan"]
