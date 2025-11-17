#!/usr/bin/env bash
set -e

# Ensure correct ownership (using default LinuxServer user "abc")
chown -R abc:abc /config
chown -R abc:abc /app/OGCS

# Run Wine setup and copy OGCS as user abc
su - abc -s /bin/bash <<'EOF'
export WINEPREFIX=/config/.wine
export WINEARCH=win64
export HOME=/config

# Initialize Wine prefix if missing
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "Initializing Wine prefix..."
    wineboot --init
    sleep 5

    echo "Installing .NET Framework 4.6.2..."
    winetricks -q dotnet462
    sleep 10
fi

# Copy OGCS to /config on first run
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Copying OGCS into /config..."
    cp -r /app/OGCS/* /config/
    chown -R abc:abc /config
fi
EOF