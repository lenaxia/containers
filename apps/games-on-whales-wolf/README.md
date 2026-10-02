# games-on-whales-wolf

Wolf (Moonlight host, [shrinedogg multi-user fork][1]) with the NVIDIA
**595.71.05** graphics userspace overlay at `/opt/nv71`.

Workaround for the Talos production-driver 595.91.07 GBM regression that
breaks wolf's Wayland compositor dmabuf imports in containers
(`EGL_BAD_ALLOC: could not bind to DMA buffer`). See the cluster repo
(`talos-ops-prod`, app `games-on-whales`) for the full forensic trail and
consumption details.

The fenrir/direwolf operator sets its own `LD_LIBRARY_PATH` on the wolf
sidecar; the cluster's `wolf-root-entrypoint` ConfigMap prepends
`/opt/nv71` before exec'ing wolf.

[1]: https://github.com/shrinedogg
