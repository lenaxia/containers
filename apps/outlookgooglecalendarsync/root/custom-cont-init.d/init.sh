#!/usr/bin/env bash
set -e

# Set environment variables
export WINEPREFIX=/config/.wine
export WINEARCH=win32   # OGCS 4.5/.NET 4.6.2 works better in 32-bit
export HOME=/config
export DISPLAY=:1

# Initialize Wine prefix if missing
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "Initializing Wine prefix..."
    wineboot --init
    sleep 5

    echo "Installing .NET Framework 4.6.2..."
    winetricks -q dotnet462
    sleep 10
fi

# Copy OGCS portable to /config on first run if missing
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Copying OGCS into /config..."
    cp -r /app/OGCS/* /config/
fi

# Note: Do NOT attempt chown, rely on fsGroup to ensure container user has permissions
