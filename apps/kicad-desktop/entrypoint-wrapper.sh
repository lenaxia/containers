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
# Selkies-GStreamer pipeline, etc.). The entrypoint ends with:
#   echo "Session Running. Press [Return] to exit."
#   read
#
# In Kubernetes there is no stdin, so `read` gets EOF immediately and the
# script exits, killing the container. We pipe "x" to satisfy `read` —
# this causes the script to exit AFTER starting all background processes
# (Xvfb, Xfce4, GStreamer). Then we block forever with tail.
#
# Background processes (Xvfb, Xfce4) survive because they are reparented
# to PID 1 (this shell) when the entrypoint subshell exits.
/etc/entrypoint.sh <<< "x" || true

# Keep the container alive after the entrypoint exits.
exec tail -f /dev/null
