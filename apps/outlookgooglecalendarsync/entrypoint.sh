#!/bin/bash
set -e

# Ensure /config exists (mounted volume)
mkdir -p /config

# Copy files from staging folder if they are not already present in /config
if [ ! -f /config/OutlookGoogleCalendarSync.exe ]; then
    echo "Copying OGCS files to /config..."
    cp -r /app/OGCS-dist/* /config/
fi

# Initialize Wine prefix if needed
wineboot --init || true

# Launch OGCS under Wine
exec wine /config/OutlookGoogleCalendarSync.exe