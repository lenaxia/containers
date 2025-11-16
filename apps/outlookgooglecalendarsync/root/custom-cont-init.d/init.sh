#!/bin/bash

# Set permissions first
chown abc:abc /app -R
chown abc:abc /config -R

# Copy OGCS files if not present
if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Initializing OGCS in /config..."
    cp -r /app/OGCS/* /config/
    chown abc:abc /config -R
fi

# Initialize Wine prefix as the abc user if needed
if [ ! -d "/config/.wine" ] || [ ! -f "/config/.wine/system.reg" ]; then
    echo "Initializing Wine prefix..."
    su -s /bin/bash -c '
        export WINEPREFIX=/config/.wine
        export WINEARCH=win64
        export HOME=/config
        export DISPLAY=:1
        wineboot --init
    ' abc
    chown abc:abc /config -R
fi

chmod +x /defaults/autostart