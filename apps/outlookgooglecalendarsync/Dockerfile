# Base image with lightweight desktop + VNC
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

LABEL maintainer="mail@suki.buzz"

# OGCS version
ARG OGCS_VERSION="3.0.0.30"

# Wine environment
ENV WINEPREFIX=/config/wine \
    WINEARCH=win32 \
    HOME=/config \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all"

# Install Wine + tools + Firefox
RUN apt-get update && \
    apt-get install -y wine64 wine32 winetricks p7zip-full wget curl unzip inotify-tools rsync openbox firefox-esr && \
    rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /app/OGCS-dist /config /downloads

# Set working dir
WORKDIR /app/OGCS-dist

# Download and extract OGCS portable ZIP into staging folder
RUN curl -L -o /downloads/OGCS.zip "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${OGCS_VERSION}.zip" && \
    7z x /downloads/OGCS.zip -o/app/OGCS-dist && \
    rm /downloads/OGCS.zip

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose VNC port (for desktop access if needed)
EXPOSE 3000

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]