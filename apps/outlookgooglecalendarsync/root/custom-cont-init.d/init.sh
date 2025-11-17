#!/usr/bin/env bash
set -e

# Ensure correct ownership (using default LinuxServer user "abc")
chown abc:abc /config -R
chown abc:abc /app/OGCS -R

# Run as abc user for Wine operations
su -s /bin/bash abc << 'EOF'
export WINEPREFIX=/config/.wine
export WINEARCH=win64
export HOME=/config
export DISPLAY=:1

# If prefix is uninitialized, do it and install .NET
if [ ! -f "$WINEPREFIX/system.reg" ]; then
  echo "Initializing Wine prefix..."
  wineboot --init
  sleep 5

  echo "Installing .NET Framework 4.6.2..."
  winetricks -q dotnet462

  echo "Waiting for .NET install to finish..."
  sleep 10
fi

# On first run, copy OGCS
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
  echo "Copying OGCS into /config..."
  cp -r /app/OGCS/* /config/
  chown abc:abc /config -R
fi

