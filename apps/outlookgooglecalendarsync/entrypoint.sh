#!/bin/bash
set -e

# Ensure config directory exists
mkdir -p /config

# Set Wine environment
export WINEPREFIX=/config/wine
export WINEARCH=win64
export DISPLAY=:1
export WINEDLLOVERRIDES="mscoree,mshtml="
export WINEDEBUG="-all"

# Copy OGCS portable files to /config on first run
if [ ! -f /config/OutlookGoogleCalendarSync.exe ]; then
    echo "Initializing OGCS in /config..."
    cp -r /app/OGCS-dist/* /config/
fi

# Initialize wine prefix (first run)
if [ ! -d "$WINEPREFIX" ] || [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "Initializing Wine prefix..."
    wineboot --init
    # Install core Wine dependencies
    winetricks -q mono corefonts vcrun6 vcrun2015 || true
fi

# Launch OGCS in GUI mode
echo "Launching OGCS..."
exec wine64 /config/OutlookGoogleCalendarSync.exe