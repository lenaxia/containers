#!/bin/bash

if [ ! -f "/config/OutlookGoogleCalendarSync.exe" ]; then
    echo "Initializing OGCS in /config..."
    cp -r /app/OGCS/* /config/
fi

if [ ! -d "/config/wine" ] || [ ! -f "/config/wine/system.reg" ]; then
    echo "Initializing Wine prefix..."
    export WINEPREFIX=/config/wine
    export WINEARCH=win64
    wineboot --init
    
    echo "Installing Wine Mono for .NET support..."
    winetricks -q mono || true
fi

chown abc:abc /app -R
chown abc:abc /config -R

chmod +x /defaults/autostart