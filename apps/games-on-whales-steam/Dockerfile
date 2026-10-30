# syntax=docker/dockerfile:1
#
# games-on-whales Steam (gamescope-wl build) + NVIDIA 595.71.05
# graphics userspace overlay.
#
# WHY: the Talos production-track driver 595.91.07 ships a regressed GBM
# allocator path in containers (no ARGB formats, no modifiers, render
# nodes dead — EGL dmabuf imports fail with EGL_BAD_ALLOC). The 595.71.05
# userspace, loaded ahead of the injected .91 set, restores the full
# allocation/import chain against the SAME .91 kernel driver (verified
# live on the cluster 2026-10-01: gst waylanddisplaysrc CUDAMemory
# pipeline goes PLAYING with .71 userspace where .91 dies in 30ms).
# CUDA libs ship as .71 too: a mixed .71 EGL + .91 libcuda stack makes
# eglQueryDevicesEXT fail with EGL_BAD_ALLOC (EGL-CUDA interop version
# check) killing the compositor. NVENC against the .91 kernel then fails
# cleanly and wolf falls back to software x264/x265 encode.
#
# The operator (fenrir/direwolf) injects its own LD_LIBRARY_PATH for the
# wolf sidecar; the wolf-root-entrypoint ConfigMap in the cluster repo
# prepends /opt/nv71 to it before exec'ing wolf. This image only needs to
# carry the files at a path nothing else claims.

FROM ubuntu:24.04 AS fetch

ARG NVIDIA_RUN_URL=https://us.download.nvidia.com/XFree86/Linux-x86_64/595.71.05/NVIDIA-Linux-x86_64-595.71.05.run
ARG NVIDIA_RUN_SHA256=56662e512d860e10493a2df2b7508c74:1777372907.091337

RUN --mount=type=cache,target=/nvidia/cache \
    apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates \
    && curl -fsSL -o /tmp/nvidia.run "${NVIDIA_RUN_URL}" \
    && sh /tmp/nvidia.run -x --target /tmp/nvx >/dev/null \
    && mkdir -p /nv71 \
    && cd /nv71 \
    && cp /tmp/nvx/libcuda.so.595.71.05 \
          /tmp/nvx/libnvidia-ptxjitcompiler.so.595.71.05 \
          /tmp/nvx/libnvidia-nvvm.so.595.71.05 \
          /tmp/nvx/libnvidia-nvvm70.so.4 \
          /tmp/nvx/libnvidia-allocator.so.595.71.05 \
          /tmp/nvx/libnvidia-eglcore.so.595.71.05 \
          /tmp/nvx/libnvidia-glcore.so.595.71.05 \
          /tmp/nvx/libnvidia-glsi.so.595.71.05 \
          /tmp/nvx/libnvidia-tls.so.595.71.05 \
          /tmp/nvx/libnvidia-glvkspirv.so.595.71.05 \
          /tmp/nvx/libnvidia-gpucomp.so.595.71.05 \
          /tmp/nvx/libnvidia-ml.so.595.71.05 \
          /tmp/nvx/libnvidia-cfg.so.595.71.05 \
          /tmp/nvx/libEGL_nvidia.so.595.71.05 \
          /tmp/nvx/libGLX_nvidia.so.595.71.05 \
          /tmp/nvx/libGLESv2_nvidia.so.595.71.05 \
          /tmp/nvx/libGLESv1_CM_nvidia.so.595.71.05 \
          /tmp/nvx/libnvidia-egl-wayland.so.1.1.20 \
          /tmp/nvx/libnvidia-egl-wayland2.so.1.0.1 \
          /tmp/nvx/libnvidia-wayland-client.so.595.71.05 \
          /tmp/nvx/libnvidia-egl-gbm.so.1.1.3 \
          /tmp/nvx/10_nvidia_wayland.json \
          /tmp/nvx/09_nvidia_wayland2.json \
          /tmp/nvx/15_nvidia_gbm.json \
          /tmp/nvx/10_nvidia.json . \
    && ln -s libEGL_nvidia.so.595.71.05 libEGL_nvidia.so.0 \
    && ln -s libGLX_nvidia.so.595.71.05 libGLX_nvidia.so.0 \
    && ln -s libGLESv2_nvidia.so.595.71.05 libGLESv2_nvidia.so.2 \
    && ln -s libGLESv1_CM_nvidia.so.595.71.05 libGLESv1_CM_nvidia.so.1 \
    && ln -s libnvidia-egl-gbm.so.1.1.3 libnvidia-egl-gbm.so.1 \
    && ln -s libnvidia-egl-wayland.so.1.1.20 libnvidia-egl-wayland.so.1 \
    && for f in *.595.71.05; do ln -s "$f" "${f%.595.71.05}.1" 2>/dev/null || true; done \
    && ln -sf libnvidia-allocator.so.595.71.05 libnvidia-allocator.so.1 \
    && ln -sf libcuda.so.595.71.05 libcuda.so.1 \
    && ln -sf libnvidia-ptxjitcompiler.so.595.71.05 libnvidia-ptxjitcompiler.so.1 \
    && ln -sf libnvidia-nvvm.so.595.71.05 libnvidia-nvvm.so.3


# Base: upstream GOW steam image (gamescope-wl era; RUN_GAMESCOPE=true).
# Renovate: digest-pinned; upstream has no version tags — bump via
# https://github.com/games-on-whales/steam/pkgs/container/steam
FROM ghcr.io/games-on-whales/steam@sha256:9b6105be7ad072a38bca221853bc1980e1403a2598fd4915f79131a21ddf2b77

# Runtime tooling: curl for the wolf unix-socket API (the base image
# is Fedora-family). microdnf first (container image), dnf fallback.
RUN (command -v microdnf >/dev/null && microdnf install -y curl ca-certificates) \
    || (dnf install -y curl ca-certificates && dnf clean all)

COPY --from=fetch /nv71 /opt/nv71
