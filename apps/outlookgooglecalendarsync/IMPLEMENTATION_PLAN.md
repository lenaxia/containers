# OGCS KASM Implementation Plan

## Current Issues

### 1. Wrong Initialization System
- Current: Uses custom `entrypoint.sh` with `ENTRYPOINT` directive
- Expected: KASM base image uses its own init system with:
  - `root/defaults/autostart` - defines what application to launch
  - `root/custom-cont-init.d/*.sh` - custom initialization scripts
  - No custom ENTRYPOINT needed

### 2. Missing KASM Directory Structure
Current implementation lacks:
- `root/defaults/autostart` - Application launch script
- `root/custom-cont-init.d/init.sh` - Pre-launch initialization
- Proper COPY structure (`COPY root /`)

### 3. Incorrect Dockerfile Pattern
- Current: Tries to override KASM's init with custom entrypoint
- Expected: Follow FMD2 pattern - install app, copy root structure, let KASM handle init

### 4. Wine Setup Issues
- Wine initialization happens in entrypoint (wrong place)
- Should happen in custom-cont-init.d before app launch
- WINEPREFIX should be in /config for persistence

### 5. Application Download
- Currently downloads in Dockerfile build
- Should use ARG VERSION for version management
- Download URL is hardcoded

## Implementation Plan

### Step 1: Update Dockerfile
```dockerfile
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG OGCS_VERSION="3.0.0.30"

LABEL maintainer="mail@suki.buzz"

ENV \
  WINEDLLOVERRIDES="mscoree,mshtml=" \
  WINEDEBUG="-all" \
  HOME=/config

# Install Wine and dependencies
RUN \
  apt-get update && \
  dpkg --add-architecture i386 && \
  apt-get install -y \
    wine64 \
    wine32:i386 \
    winetricks \
    wget \
    p7zip-full \
    curl \
    inotify-tools \
    rsync \
    openbox && \
  apt-get autoremove -y wget curl --purge && \
  rm -rf /var/lib/apt/lists/*

# Download and extract OGCS
RUN \
  mkdir -p /app/OGCS && \
  wget -O /tmp/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${OGCS_VERSION}.zip" && \
  7z x /tmp/OGCS.zip -o/app/OGCS && \
  rm /tmp/OGCS.zip

# Copy KASM structure
COPY root /

VOLUME /config
EXPOSE 3000
```

### Step 2: Create root/defaults/autostart
```bash
#!/bin/bash
cd /app/OGCS
wine OutlookGoogleCalendarSync.exe
```

### Step 3: Create root/custom-cont-init.d/init.sh
```bash
#!/bin/bash

# Set up Wine prefix on first run
if [ ! -d "/config/wine" ] || [ ! -f "/config/wine/system.reg" ]; then
    echo "Initializing Wine prefix..."
    export WINEPREFIX=/config/wine
    export WINEARCH=win64
    wineboot --init
    
    # Install Wine dependencies
    winetricks -q mono corefonts vcrun6 vcrun2015 || true
fi

# Set permissions
chown abc:abc /app -R
chown abc:abc /config -R

# Make autostart executable
chmod +x /defaults/autostart
```

### Step 4: Update docker-bake.hcl
```hcl
target "docker-metadata-action" {}

variable "VERSION" {
  // renovate: datasource=github-releases depName=phw198/OutlookGoogleCalendarSync
  default = "3.0.0.30"
}

variable "SOURCE" {
  default = "https://github.com/phw198/OutlookGoogleCalendarSync"
}

group "default" {
  targets = ["image-local"]
}

target "image" {
  inherits = ["docker-metadata-action"]

  args = {
    OGCS_VERSION = "${VERSION}"
  }

  labels = {
    "org.opencontainers.image.source" = "${SOURCE}"
  }
}

target "image-local" {
  inherits = ["image"]
  output = ["type=docker"]
}

target "image-all" {
  inherits = ["image"]
  platforms = [
    "linux/amd64"
  ]
}
```

### Step 5: Remove entrypoint.sh
- Delete the custom entrypoint.sh file
- KASM base image handles all initialization

## Dependencies Covered

### Wine Dependencies
- wine64 - 64-bit Wine
- wine32:i386 - 32-bit Wine support
- winetricks - Wine helper scripts
- mono (via winetricks) - .NET runtime for Wine
- vcrun6, vcrun2015 (via winetricks) - Visual C++ runtimes
- corefonts (via winetricks) - Microsoft core fonts

### System Dependencies
- p7zip-full - Extract .zip files
- wget/curl - Download OGCS
- inotify-tools - File monitoring (if needed)
- rsync - File syncing (if needed)
- openbox - Window manager (provided by KASM base)

### KASM Base Image Provides
- KasmVNC - Web-based VNC
- Kclient - Audio/file access
- NGINX - Web server
- PulseAudio - Audio
- Openbox - Desktop environment
- Init system - Container initialization

## Key Differences from FMD2

1. **Application**: OGCS vs FMD2
2. **Download method**: Direct GitHub release vs API query
3. **No sync_dir needed**: OGCS doesn't need file monitoring like FMD2
4. **Simpler setup**: No git clone of source needed

## Testing Plan

1. Build image: `docker build -t ogcs:test .`
2. Run container: `docker run --rm -it -p 3000:3000 -v ogcs-config:/config ogcs:test`
3. Access web UI: http://localhost:3000
4. Verify:
   - Wine initializes correctly
   - OGCS launches in GUI
   - Settings persist in /config
   - No errors in logs

## Migration Notes

- Users with existing setups will need to:
  - Backup /config directory
  - Rebuild with new image
  - Wine prefix will reinitialize (one-time)
  - OGCS settings should persist if stored in /config