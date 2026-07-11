# syntax=docker/dockerfile:1
#
# KiCad 10 Streaming Workstation (Intel VAAPI / Quick Sync)
#
# Single image bundling:
#   - Xvfb + Xfce4 + IceWM         (graphical session)
#   - KiCad 10 + community plugins (eeschema + pcbnew)
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
# Multi-arch: amd64 only. KiCad PPA publishes amd64 debs, and the
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
    # ── KiCad IPC API client vars (set BY kicad FOR plugins at runtime) ──
    # KICAD_API_SOCKET and KICAD_API_TOKEN are exported by kicad to its children.
    # They are referenced here only so the MCP sidecar can read them via a shared
    # volume; do NOT set them statically in production.
    KICAD_DOCUMENTS_HOME=/config/kicad

# ──────────────────────────────────────────────────────────────────────────────
# 1. KiCad 10.0 official PPA (ppa:kicad/kicad-10.0-releases).
#    The old apt.kicad.org repo was decommissioned; KiCad 10 ships via the
#    Launchpad PPA. KiCad 10's IPC API (gRPC/NNG) has meaningful improvements
#    over 9 (better headless paths, richer tool surface for the MCP server).
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
install -d -m 0755 /etc/apt/keyrings
curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xFDA854F61C4D0D9572BB95E5245D5502FAD7A805" \
    | gpg --dearmor --yes -o /etc/apt/keyrings/kicad.gpg
chmod 0644 /etc/apt/keyrings/kicad.gpg
echo "deb [signed-by=/etc/apt/keyrings/kicad.gpg] https://ppa.launchpadcontent.net/kicad/kicad-10.0-releases/ubuntu noble main" \
    > /etc/apt/sources.list.d/kicad.list
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 2. LizardByte Sunshine — download .deb from GitHub releases.
#    The old ghproxy.lizardbyte.dev apt repo is deprecated.
#    Renovate: datasource=github-releases depName=LizardByte/Sunshine
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update
SUNSHINE_VER="v2025.122.141614"
SUNSHINE_DEB="sunshine-ubuntu-24.04-amd64.deb"
curl -fsSL -o "/tmp/${SUNSHINE_DEB}" \
    "https://github.com/LizardByte/Sunshine/releases/download/${SUNSHINE_VER}/${SUNSHINE_DEB}"
apt-get install -y --no-install-recommends "/tmp/${SUNSHINE_DEB}"
rm -f "/tmp/${SUNSHINE_DEB}"
EOF

# ──────────────────────────────────────────────────────────────────────────────
# 3. KiCad 10 + WM + VAAPI + Python tooling
# ──────────────────────────────────────────────────────────────────────────────
RUN <<'EOF'
set -eux
apt-get update

# KiCad 10 from the PPA. The metapackage 'kicad' depends on kicad-cli,
# kicad-symbols, kicad-footprints, kicad-templates, and pulls in 3D models
# via recommends. Use --no-install-recommends only for the WM/VAAPI sections
# below; for KiCad itself we want the full suite including 3D packages.
apt-get install -y \
        kicad

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

# Python tooling for KiCad automation. pcbnew bindings ship inside the kicad
# package; pip-install the higher-level libs.
apt-get install -y --no-install-recommends python3-pip python3-venv
pip3 install --break-system-packages --no-cache-dir \
        kibot \
        skidl \
        kiutils

# kicad-python (the official IPC API client from the KiCad team).
# KiCad 10 improves the IPC API (gRPC/NNG) over 9 — including better headless
# paths. The client lib is installed here so the MCP sidecar can connect to
# the GUI's UNIX socket at /tmp/kicad/api.sock (shared emptyDir).
pip3 install --break-system-packages --no-cache-dir \
        kicad-python

# JLC-Plugin-for-KiCad (kicad-jlcpcb-tools successor) and InteractiveHtmlBom
# are KiCad GUI plugins installed via PCM (Plugin and Content Manager).
# We drop them into the system PCM repository path so they appear under
# "Downloaded Plugins" on first GUI start. They are *not* enabled automatically;
# the user enables them from PCM after first launch.
install -d -m 0755 /usr/local/share/kicad/10.0/3rdparty/plugins

# Download the latest tagged releases from the upstream repos and extract
# into the PCM plugins directory. Pinned to known-good versions.
install -d -m 0755 /tmp/plugins/jlc
install -d -m 0755 /tmp/plugins/ibom
curl -fsSL https://github.com/Bouni/kicad-jlcpcb-tools/archive/refs/tags/2026.04.03.tar.gz \
    | tar xzf - -C /tmp/plugins/jlc --strip-components=1 \
        --exclude='*/.github' --exclude='*/.git*'
mv /tmp/plugins/jlc "/usr/local/share/kicad/10.0/3rdparty/plugins/com_github_bouni_kicad_jlcpcb_tools"

curl -fsSL https://github.com/openscopeproject/InteractiveHtmlBom/archive/refs/tags/v2.11.2.tar.gz \
    | tar xzf - -C /tmp/plugins/ibom --strip-components=1 \
        --exclude='*/.github' --exclude='*/.git*'
mv /tmp/plugins/ibom "/usr/local/share/kicad/10.0/3rdparty/plugins/org_openscopeproject_interactivehtmlbom"

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

# supervisord in the base image logs to /var/log/supervisor/ — create it so
# the container starts cleanly. Owned by the runtime user (ubuntu, UID 1000).
RUN install -d -o 1000 -g 1000 -m 0755 /var/log/supervisor

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
ENTRYPOINT ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
CMD []
