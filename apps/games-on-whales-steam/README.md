# games-on-whales-steam

GOW Steam image (gamescope-wl era) with the NVIDIA **595.71.05** graphics
userspace overlay at `/opt/nv71` — same workaround as
`games-on-whales-wolf` (Talos 595.91.07 GBM regression; details in the
cluster repo). The cluster's Steam App CR startup command prepends
`/opt/nv71` to `LD_LIBRARY_PATH` before `/entrypoint.sh`.
