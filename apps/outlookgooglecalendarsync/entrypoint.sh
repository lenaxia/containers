#!/bin/bash
set -e

mkdir -p /config

# Copy OGCS portable files to /config on first run
if [ ! -f /config/OutlookGoogleCalendarSync.exe ]; then
    echo "Initializing OGCS in /config..."
    cp -r /app/OGCS-dist/* /config/
fi

# Initialize wine prefix
wineboot --init || true

# Launch OGCS
exec wine /config/OutlookGoogleCalendarSync.exe