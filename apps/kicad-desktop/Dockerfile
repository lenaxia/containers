# syntax=docker/dockerfile:1
#
# KiCad 9 Streaming Workstation (Intel VAAPI / Quick Sync)
#
# Single image bundling:
#   - Xvfb + Xfce4 + IceWM         (graphical session)
#   - KiCad 9 + community plugins  (eeschema + pcbnew)
#   - Selkies-GStreamer             (browser WebRTC, H.264 via VAAPI)
#   - Sunshine                      (Moonlight native-client host, VAAPI)
#   - supervisord                   (process supervisor)
#
# Both Selkies and Sunshine attach to the SAME X server (DISPLAY=:20), so a
# browser user and a Moonlight user see the same KiCad session.
#
# Built as a layer on top of the upstream Selkies-GStreamer reference desktop
# image (Ubuntu 24.04 + Xvfb + VAAPI + GStreamer + supervisord). KiCad, Sunshine,
# and IceWM are added on top.
#
# Target node: Intel NUC8i5 (Iris Plus 655). Use the gpu.intel.com/i915
# device plugin to mount /dev/dri into the pod.
#
# Multi-arch: amd64 only. KiCad 9.0 upstream publishes amd64 debs, and the
# Intel iGPU target is x86_64-only.

ARG TARGETARCH
# Selkies publishes only amd64 tags for the example desktop image today.
# Pin by digest in production; the bake.hcl pins the tag.
FROM ghcr.io/selkies-project/selkies-gstreamer/gst-py-example:main-ubuntu24.04
ARG TARGETARCH
ARG VERSION
ARG VENDOR

# Selkies base sets USER ubuntu (UID 1000) — switch to root for apt installs.
USER root

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    # ── Selkies runtime knobs (override at runtime via k8s env) ──────────────
    SELKIES_ENCODER=vah264enc \
    SELKIES_FRAMERATE=60 \
    SELKIES_VIDEO_BITRATE=8 \
    SELKIES_AUDIO_BITRATE=128000 \
    SELKIES_GPU_ID=0 \
    DISPLAY=:20 \
    # ── KiCad 9 IPC API client vars (set BY kicad FOR plugins at runtime) ──
    # KICAD_API_SOCKET and KICAD_API_TOKEN are exported by kicad to its children.
    # They are referenced here only so the MCP sidecar can read them via a shared
    # volume; do NOT set them statically in production.
    KICAD_DOCUMENTS_HOME=/config/kicad

# ──────────────────────────────────────────────────────────────────────────────
# 1. KiCad 9.0 official apt repo
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
# KiCad's repo signing key (kicad.org/gtest.asc; this is the documented path
# from https://dev.kicad.org/kicad-addons/ ).
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://kicad.org/gtest.asc \
    | gpg --dearmor --yes -o /etc/apt/keyrings/kicad.gpg
chmod 0644 /etc/apt/keyrings/kicad.gpg

# kicad-9.0 release channel. See https://packages.debian.org and
# https://dev.kicad.org/linux/ for the suite name.
echo "deb [signed-by=/etc/apt/keyrings/kicad.gpg] http://apt.kicad.org kicad-9.0 main" \
    > /etc/apt/sources.list.d/kicad.list

# Pre-seed debconf so apt doesn't prompt for the kicad-common fonts EULA.
echo "resconf kicad-common kicad-common/accepted_eula boolean true" | debconf-set-selections
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 2. LizardByte Sunshine apt repo (for Moonlight host)
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
# LizardByte publishes an apt repo at lizardbyte.dev. Read it via the
# GitHub proxy they document at https://docs.lizardbyte.dev/sunshine/latest/.
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://ghproxy.lizardbyte.dev/__github__/LizardByte/.github/raw/master/keys/sunshine \
    | gpg --dearmor --yes -o /etc/apt/keyrings/sunshine.gpg
chmod 0644 /etc/apt/keyrings/sunshine.gpg

# The repo is keyed to the *Ubuntu release name*. The Selkies base is
# ubuntu:24.04 (noble). Update if you rebase.
. /etc/os-release
echo "deb [signed-by=/etc/apt/keyrings/sunshine.gpg] http://ghproxy.lizardbyte.dev/__github__/LizardByte/.github/deb/ubuntu ${UBUNTU_CODENAME:-noble} main" \
    > /etc/apt/sources.list.d/sunshine.list
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 3. KiCad 9 + Sunshine + WM + VAAPI + Python tooling
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update

# KiCad 9 (full meta + libs + 3D models). Pin to 9.0.* so a future 9.1 in the
# repo doesn't silently change behaviour. The metapackage 'kicad' depends on
# kicad-cli, kicad-symbols, kicad-footprints, kicad-templates, kicad-packages3d.
apt-get install -y --no-install-recommends \
        kicad=9.0.* \
        kicad-libraries \
        kicad-packages3d \
        python3-kicad-pcbnew

# Sunshine (Moonlight host). Brings in libboost, libva, libavcodec, miniupnpc.
apt-get install -y --no-install-recommends sunshine

# Window managers: keep Xfce4 from base image as the full session; add IceWM
# as an ultra-lightweight fallback WM (no compositor, no panel) for users who
# want maximum GPU cycles for KiCad's 3D viewer.
apt-get install -y --no-install-recommends icewm

# Intel VAAPI stack (already present on the Selkies base, but be explicit so a
# future rebase doesn't drop them silently). i965 is needed for the Iris Plus
# 655 (Kaby Lake R); intel-media-va-driver-non-free covers newer gens.
apt-get install -y --no-install-recommends \
        intel-media-va-driver-non-free \
        i965-va-driver-shaders \
        mesa-va-drivers \
        libva2 \
        vainfo \
        libva-drm2 \
        libva-x11-2 \
        libva-glx2

# Fonts so KiCad renders schematics/PCB text consistently.
apt-get install -y --no-install-recommends \
        fonts-dejavu \
        fonts-liberation \
        fonts-liberation2

# Python tooling for KiCad automation. pcbnew bindings come from the
# python3-kicad-pcbnew package above; pip-install the higher-level libs.
apt-get install -y --no-install-recommends python3-pip python3-venv
pip3 install --break-system-packages --no-cache-dir \
        kibot \
        skidl \
        kiutils

# kicad-python (the official IPC API client from the KiCad team).
# KiCad 9 IPC API is PCB-editor-only and requires the GUI to be running, but
# the client lib is installed here so the MCP sidecar can connect to the GUI's
# UNIX socket (mounted into the pod via an emptyDir at /tmp/kicad).
pip3 install --break-system-packages --no-cache-dir \
        kicad-python

# JLC-Plugin-for-KiCad (kicad-jlcpcb-tools successor) and InteractiveHtmlBom
# are KiCad GUI plugins installed via PCM (Plugin and Content Manager).
# We drop them into the system PCM repository path so they appear under
# "Downloaded Plugins" on first GUI start. They are *not* enabled automatically;
# the user enables them from PCM after first launch.
install -d -m 0755 /usr/local/share/kicad/9.0/3rdparty/plugins

# Download the latest tagged releases from the upstream repos and extract
# into the PCM plugins directory. Pinned to known-good versions.
install -d -m 0755 /tmp/plugins
curl -fsSL https://github.com/Bouni/kicad-jlcpcb-tools/archive/refs/tags/v2025.4.0.tar.gz \
    | tar xzf - -C /tmp/plugins --strip-components=1 \
        --exclude='*/.github' --exclude='*/.git*'
mv /tmp/plugins "/usr/local/share/kicad/9.0/3rdparty/plugins/com_github_bouni_kicad_jlcpcb_tools"

curl -fsSL https://github.com/openscopeproject/InteractiveHtmlBom/archive/refs/tags/2.11.1.tar.gz \
    | tar xzf - -C /tmp/plugins --strip-components=1 \
        --exclude='*/.github' --exclude='*/.git*'
mv /tmp/plugins "/usr/local/share/kicad/9.0/3rdparty/plugins/org_openscopeproject_interactivehtmlbom"

rm -rf /tmp/plugins

# Cleanup
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 4. Supervisord drop-ins: add Sunshine + KiCad autostart to the base image's
#    supervisord-managed process tree (Xvfb, Xfce4, pipewire, selkies-gstreamer,
#    nginx, coturn). The Selkies base image loads /etc/supervisor/conf.d/*.conf.
# ──────────────────────────────────────────────────────────────────────────────
COPY sunshine.conf /etc/supervisor/conf.d/sunshine.conf
COPY kicad-autostart.desktop /etc/xdg/autostart/kicad.desktop

# Make sure the Sunshine config dir is owned by the runtime user.
RUN install -d -o 1000 -g 1000 -m 0755 /config/sunshine

# Switch back to the Selkies base runtime user (UID 1000 = ubuntu).
USER ubuntu:ubuntu
WORKDIR /home/ubuntu

# Ports:
#   8080/tcp   Selkies browser UI (NGINX)            — exposed via Traefik IngressRoute
#   8081/tcp   Selkies signalling (loopback only)
#   9081/tcp   Selkies Prometheus metrics
#   3478/tcp+udp  coturn TURN
#   47984/tcp  Sunshine HTTPS control (pairing)
#   47989/tcp  Sunshine HTTP control
#   47990/tcp  Sunshine Web UI
#   47998-48000/udp  Sunshine media (video/control/audio)
#   48010/tcp  Sunshine RTSP setup
EXPOSE 8080 8081 9081 3478 47984 47989 47990 48010

# Inherit the Selkies base image's entrypoint (supervisord). All behavior is
# driven by env vars and the supervisord config files.
ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
CMD []
