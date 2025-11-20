#!/usr/bin/env bash
set -e

export HOME=/config
export WINEPREFIX=/config/.wine
export WINEARCH=win32
export DISPLAY=:0

# Only create Wine prefix if missing
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "Creating Wine prefix with extra space..."
    rm -rf "$WINEPREFIX"
    mkdir -p "$WINEPREFIX"

    # Winetricks .NET and fonts
    echo "Installing .NET 4.6.2..."
    s6-setuidgid abc winetricks -q dotnet462 corefonts
fi

# Copy OGCS on first run
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Copying OGCS into /config..."
    cp -r /app/OGCS/* /config/
fi

