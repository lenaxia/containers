#!/usr/bin/env bash
set -e

export HOME=/config
export WINEPREFIX=/config/.wine
export WINEARCH=win32
export DISPLAY=:1

# Initialize Wine prefix as user "abc" (PUID 1000)
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "Initializing Wine prefix as abc..."
    s6-setuidgid abc wineboot --init
    sleep 5

    echo "Installing .NET 4.6.2..."
    s6-setuidgid abc winetricks -q dotnet462 corefonts
    sleep 10
fi

# Copy OGCS portable to /config on first run
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Copying OGCS into /config..."
    cp -r /app/OGCS/* /config/
    chown -R abc:abc /config
fi

