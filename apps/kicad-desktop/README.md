# kicad-desktop

KiCad 9 streaming workstation — **Selkies-GStreamer** (browser WebRTC) and
**Sunshine** (Moonlight native client) sharing one X server, with Intel
VAAPI/QSV hardware encoding.

Built and used by the [talos-ops-prod](https://github.com/lenaxia/talos-ops-prod)
cluster — see `docs/kicad-streaming-workstation.md` in that repo for the full
deployment guide.

## What's in the image

Layered on `ghcr.io/selkies-project/selkies-gstreamer/gst-py-example:main-ubuntu24.04`:

- **KiCad 9.0** — full meta + libs + 3D models (from `apt.kicad.org`)
- **Sunshine** — Moonlight host (from LizardByte apt repo)
- **IceWM** — lightweight WM fallback (in addition to Xfce4 from base)
- **Intel VAAPI stack** — `intel-media-va-driver-non-free`, `i965-va-driver-shaders`, `mesa-va-drivers`, `libva2`, `vainfo`
- **Python tooling** — `kibot`, `skidl`, `kiutils`, `kicad-python` (IPC API client)
- **KiCad plugins** (pre-extracted into system PCM path):
  - [JLC-Plugin-for-KiCad](https://github.com/Bouni/kicad-jlcpcb-tools) (`com_github_bouni_kicad_jlcpcb_tools`)
  - [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) (`org_openscopeproject_interactivehtmlbom`)
- **supervisord drop-in** — adds Sunshine as a managed process alongside the
  Selkies stack (Xvfb + Xfce4 + pipewire + selkies-gstreamer + nginx + coturn)
- **XDG autostart** — KiCad launches automatically when the Xfce4 session starts

## Runtime requirements

| Resource | Value |
|---|---|
| `/dev/dri` | Required. Pass via `gpu.intel.com/i915: 1` resource request (Intel GPU plugin). |
| `/dev/uinput` | Optional (only for Sunshine virtual input). Add `input` supplemental group. |
| Pod IPC namespace | Recommend `shareProcessNamespace: true` for MIT-SHM speedup (Selkies + Sunshine + X). |
| User | `ubuntu` (UID 1000, inherited from Selkies base) |
| CPU request | 1000m (KiCad's 3D viewer is CPU-heavy under Xvfb's llvmpipe GL) |
| Memory limit | 8Gi minimum |

## Ports

| Port | Protocol | Service |
|---|---|---|
| 8080 | TCP | Selkies browser UI (NGINX) |
| 8081 | TCP | Selkies signalling (loopback) |
| 9081 | TCP | Selkies Prometheus metrics |
| 3478 | TCP+UDP | coturn TURN |
| 47984 | TCP | Sunshine HTTPS control + pairing |
| 47989 | TCP | Sunshine HTTP control |
| 47990 | TCP | Sunshine Web UI (HTTPS) |
| 47998-48000 | UDP | Sunshine media streams |
| 48010 | TCP | Sunshine RTSP setup |

## Environment variables

The Selkies base image reads a large set of `SELKIES_*` env vars. The ones
that matter most for this deployment:

| Var | Default | Effect |
|---|---|---|
| `SELKIES_ENCODER` | `vah264enc` | Intel VAAPI H.264 (Quick Sync). Other stable options: `x264enc` (software), `vah265enc` (HEVC, marked unstable). |
| `SELKIES_FRAMERATE` | `60` | 8-120 |
| `SELKIES_VIDEO_BITRATE` | `8` | Mbps, 1-100 |
| `SELKIES_GPU_ID` | `0` | Index into `/dev/dri/renderD*` (0 → renderD128) |
| `SELKIES_BASIC_AUTH_PASSWORD` | (from Secret) | Browser UI password (user defaults to `ubuntu`) |
| `DISPLAY` | `:20` | X server the Selkies+Sunshine processes share |

Sunshine does **not** read env vars for ports or credentials. First-run
Web UI credentials are set via `sunshine creds <user> <pass>` (see deployment
guide).

## Verification (inside the running pod)

```bash
# VAAPI works?
vainfo
# Expect: "VAEntrypointEncSlice" for VAProfileH264High and friends.

# GStreamer VAAPI plugin loaded?
gst-inspect-1.0 vah264enc
# Expect: a non-empty description, no "no such element" error.

# KiCad installed?
kicad-cli version
kicad version

# Sunshine installed?
sunshine version
```

## Local dev

```bash
# Build
docker buildx bake image-local

# Run (requires /dev/dri on host)
docker run --rm -it \
    --device /dev/dri:/dev/dri \
    -p 8080:8080 -p 47984-47990:47984-47990/tcp -p 48010:48010/tcp \
    -p 47998-48000:47998-48000/udp \
    -e SELKIES_BASIC_AUTH_PASSWORD=changeme \
    -v "$PWD/projects:/projects" \
    ghcr.io/lenaxia/kicad-desktop:latest

# Browse to:
#   http://localhost:8080/         (Selkies browser UI)
#   https://localhost:47990/       (Sunshine Web UI, self-signed cert)
```
