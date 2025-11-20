# syntax=docker/dockerfile:1
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG OGCS_VERSION="3.0.0.30"
LABEL maintainer="mail@suki.buzz"

# Environment variables
ENV HOME=/config \
    WINEPREFIX=/config/.wine \
    WINEARCH=win32 \
    DISPLAY=:0 \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all"

# Install dependencies, WineHQ repo, Wine, and Winetricks
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y wget curl gnupg2 software-properties-common p7zip-full inotify-tools rsync openbox python3 python3-xdg xvfb && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources && \
    apt-get update && \
    apt-get install -y --install-recommends winehq-stable winetricks && \
    rm -rf /var/lib/apt/lists/*

# Initialize Wine prefix and install .NET 4.5 + core fonts
RUN mkdir -p $WINEPREFIX && \
    wineboot --init && \
    winetricks -q dotnet45 corefonts && \
    while pgrep wineserver >/dev/null; do sleep 1; done

# Download OGCS portable
RUN mkdir -p /app/OGCS && \
    wget -O /tmp/OGCS.zip "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${OGCS_VERSION}.zip" && \
    7z x /tmp/OGCS.zip -o/app/OGCS && \
    rm /tmp/OGCS.zip

# Copy initialization scripts and defaults
COPY root/ /

# Pre-create nginx temp dir (writable) and fix permissions
RUN mkdir -p /var/lib/nginx/body && chown -R 1000:1000 /var/lib/nginx /config

# Expose Kasm port
EXPOSE 3000

# Persistent config
VOLUME /config

