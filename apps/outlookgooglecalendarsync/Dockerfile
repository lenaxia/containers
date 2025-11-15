# Use base KasmVNC image with desktop environment
ARG VERSION
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

LABEL maintainer="mail@suki.buzz"

# Wine environment variables
ENV WINEPREFIX=/config/wine \
    WINEARCH=win64 \
    HOME=/config \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEDEBUG="-all" \
    DISPLAY=:1

# Add i386 architecture (needed for some Wine dependencies)
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y \
      wine64 \
      wine32:i386 \
      winetricks \
      p7zip-full \
      unzip \
      curl \
      rsync \
      openbox \
      inotify-tools \
      fonts-liberation \
      x11-utils \
      xvfb \
      dbus-x11 \
      xterm \
    && rm -rf /var/lib/apt/lists/*

# Prepare directories
RUN mkdir -p /app/OGCS-dist /config /downloads

WORKDIR /app/OGCS-dist

# Download and extract OGCS
RUN wget -O /downloads/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v3.0.0.30.zip" && \
    7z x /downloads/OGCS.zip -o/app/OGCS-dist && \
    rm /downloads/OGCS.zip

# Install Wine Mono & VC runtimes via winetricks (required for .NET apps)
RUN winetricks -q mono corefonts vcrun6 vcrun2015

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose VNC & web ports (Kasm defaults)
EXPOSE 3000 6901

ENTRYPOINT ["/entrypoint.sh"]