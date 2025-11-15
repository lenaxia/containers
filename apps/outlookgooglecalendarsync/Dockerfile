# Use VERSION passed by bake
ARG VERSION
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

LABEL maintainer="mail@suki.buzz"

# Wine environment variables
ENV WINEPREFIX=/config/wine \
    WINEARCH=win32 \
    HOME=/config \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all"

# Add i386 architecture for Wine and install dependencies + Firefox (deb)
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y wget gpg && \
    install -d -m 0755 /etc/apt/keyrings && \
    wget -qO- https://packages.mozilla.org/apt/repo-signing-key.gpg | gpg --dearmor > /etc/apt/keyrings/packages.mozilla.org.gpg && \
    printf "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.gpg] https://packages.mozilla.org/apt mozilla main\n" \
      > /etc/apt/sources.list.d/mozilla.list && \
    apt-get update && \
    apt-get install -y \
      wine64 \
      wine32:i386 \
      wine32-preloader \
      winetricks \
      p7zip-full \
      unzip \
      curl \
      rsync \
      openbox \
      inotify-tools \
      firefox \
    && rm -rf /var/lib/apt/lists/*

# Prepare directories
RUN mkdir -p /app/OGCS-dist /config /downloads

WORKDIR /app/OGCS-dist

# Download OGCS portable ZIP into staging folder
RUN wget -O /downloads/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v3.0.0.30.zip" && \
    7z x /downloads/OGCS.zip -o/app/OGCS-dist && \
    rm /downloads/OGCS.zip

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/entrypoint.sh"]