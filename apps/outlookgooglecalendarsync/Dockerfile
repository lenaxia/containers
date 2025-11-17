# syntax=docker/dockerfile:1
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG OGCS_VERSION="3.0.0.30"
LABEL maintainer="mail@suki.buzz"

ENV WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all" \
    HOME=/config \
    WINEPREFIX=/config/.wine \
    WINEARCH=win64

# Fix /tmp/.X11-unix for non-root X server
USER root
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Install dependencies
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y wget curl gnupg2 software-properties-common p7zip-full inotify-tools rsync openbox python3 python3-xdg && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources && \
    apt-get update && \
    apt-get install -y --install-recommends winehq-stable winetricks && \
    rm -rf /var/lib/apt/lists/*

# Download OGCS portable
RUN mkdir -p /app/OGCS && \
    wget -O /tmp/OGCS.zip "https://github.com/user-attachments/files/22068496/Portable_OGCS_v3.0.0.30.zip" && \
    7z x /tmp/OGCS.zip -o/app/OGCS && \
    rm /tmp/OGCS.zip

# Copy init scripts and autostart
COPY root/ /

VOLUME /config
EXPOSE 3000

# Switch back to default user
USER abc