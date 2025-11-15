# Base image
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG VERSION="3.0.0.30"
LABEL maintainer="mail@suki.buzz"

ENV WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all" \
    HOME=/config \
    DISPLAY=:1

# Install Wine, Firefox, and required tools
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        wine64 \
        winetricks \
        p7zip-full \
        wget \
        unzip \
        inotify-tools \
        rsync \
        openbox \
        firefox \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /downloads /app/OGCS-dist /app/OGCS-runtime /config

# Download and extract OGCS portable
RUN wget -O /downloads/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${VERSION}.zip" && \
    7z x /downloads/OGCS.zip -o/app/OGCS-dist && \
    rm /downloads/OGCS.zip

# Copy helper scripts for staging
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Setup container entrypoint to copy staging folder to runtime folder
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Expose VNC port for Kasm if needed
EXPOSE 3000

VOLUME /config