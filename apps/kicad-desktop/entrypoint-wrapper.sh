#!/bin/bash
set -e

# Start Sunshine in the background once the X server is ready.
# The Selkies entrypoint blocks on `read`, so we fork a subshell that
# waits for the X socket, then launches Sunshine.
(
    export DISPLAY="${DISPLAY:-:20}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
    export PULSE_SERVER="${PULSE_SERVER:-unix:${XDG_RUNTIME_DIR}/pulse/native}"

    # Wait for X server
    until [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; do sleep 0.5; done

    echo "X server ready, starting Sunshine..."
    exec /usr/bin/sunshine /config/sunshine/sunshine.conf
) &
SUNSHINE_PID=$!

# Execute the Selkies base image entrypoint (starts Xvfb, Xfce4,
# Selkies-GStreamer, NGINX, etc.). This script blocks on `read`.
exec /etc/entrypoint.sh
