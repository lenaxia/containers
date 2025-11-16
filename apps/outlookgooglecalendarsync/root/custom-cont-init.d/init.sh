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

# Initialize Wine prefix and install Mono as the abc user
if [ ! -d "/config/.wine" ] || [ ! -f "/config/.wine/system.reg" ]; then
    echo "Initializing Wine prefix..."
    su -s /bin/bash abc << 'EOF'
        export WINEPREFIX=/config/.wine
        export WINEARCH=win64
        export HOME=/config
        export DISPLAY=:1
        
        echo "Creating Wine prefix..."
        wineboot --init
        
        echo "Waiting for wineboot to complete..."
        sleep 5
        
        if [ ! -d "/config/.wine/drive_c/windows/mono" ]; then
            echo "Installing Wine Mono..."
            MONO_MSI=$(ls /usr/share/wine/mono/wine-mono-*.msi 2>/dev/null | head -1)
            if [ -n "$MONO_MSI" ]; then
                echo "Found Mono MSI: $MONO_MSI"
                wine msiexec /i "$MONO_MSI" /qn
                echo "Waiting for Mono installation to complete..."
                sleep 10
            else
                echo "ERROR: Wine Mono MSI not found!"
            fi
        fi
EOF
    chown abc:abc /config -R
fi

chmod +x /defaults/autostart