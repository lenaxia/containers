#!/bin/bash
set -e

# Create XDG_RUNTIME_DIR before the Selkies entrypoint needs it.
# In a container there is no PAM session to create this automatically.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start Sunshine in the background once the X server is ready.
# The Selkies entrypoint blocks on `read`, so we fork a subshell that
# waits for the X socket, then launches Sunshine.
(
    export DISPLAY="${DISPLAY:-:20}"
    export PULSE_SERVER="${PULSE_SERVER:-unix:${XDG_RUNTIME_DIR}/pulse/native}"

    # Wait for X server
    until [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; do sleep 0.5; done

    echo "X server ready, starting Sunshine..."
    exec /usr/bin/sunshine /config/sunshine/sunshine.conf
) &

# Execute the Selkies base image entrypoint (starts Xvfb, Xfce4,
# Selkies-GStreamer, NGINX, etc.). This script blocks on `read`.
exec /etc/entrypoint.sh
