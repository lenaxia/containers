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
        
        # Install Wine Mono if not already installed
        if [ ! -d "/config/.wine/drive_c/windows/mono" ]; then
            echo "Installing Wine Mono..."
            MONO_MSI=$(ls /usr/share/wine/mono/wine-mono-*.msi 2>/dev/null | head -1)
            if [ -n "$MONO_MSI" ]; then
                wine msiexec /i "$MONO_MSI" /qn
            fi
        fi
    ' abc
    chown abc:abc /config -R
fi

chmod +x /defaults/autostart