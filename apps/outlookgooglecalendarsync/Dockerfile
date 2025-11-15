# Use VERSION passed by bake (e.g., v3.0.0.30)
ARG VERSION
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

LABEL maintainer="mail@suki.buzz"

# Wine environment variables
ENV WINEPREFIX=/config/wine \
    WINEARCH=win32 \
    HOME=/config \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all"

# Install Wine + tools + Firefox
RUN apt-get update && \
    apt-get install -y wine64 wine32 winetricks p7zip-full wget curl unzip inotify-tools rsync openbox firefox-esr && \
    rm -rf /var/lib/apt/lists/*

# Prepare dirs
RUN mkdir -p /app/OGCS-dist /config /downloads

WORKDIR /app/OGCS-dist

# Download OGCS portable ZIP into staging folder
RUN curl -L -o /downloads/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${VERSION}.zip" && \
    7z x /downloads/OGCS.zip -o/app/OGCS-dist && \
    rm /downloads/OGCS.zip

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/entrypoint.sh"]