# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG OGCS_VERSION="3.0.0.30"

LABEL maintainer="mail@suki.buzz"

ENV \
  WINEDLLOVERRIDES="mscoree,mshtml=" \
  WINEDEBUG="-all" \
  HOME=/config

RUN \
  apt-get update && \
  dpkg --add-architecture i386 && \
  apt-get install -y wget curl && \
  mkdir -pm755 /etc/apt/keyrings && \
  wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
  wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources && \
  apt-get update && \
  apt-get install -y \
    --install-recommends \
    winehq-stable \
    p7zip-full \
    inotify-tools \
    rsync \
    python3-pyxdg \
    openbox && \
  rm -rf /var/lib/apt/lists/*

RUN \
  echo "Fetching Wine Mono version from Wine source..." && \
  WINE_VER=$(wine --version | grep -oP 'wine-\K[0-9]+\.[0-9]+' | head -1) && \
  echo "Wine version: ${WINE_VER}" && \
  WINE_MONO_VERSION=$(wget -q -O- "https://raw.githubusercontent.com/wine-mirror/wine/wine-${WINE_VER}/dlls/appwiz.cpl/addons.c" | \
    grep -E "^#define MONO_VERSION\s" | awk -F\" '{print $2}') && \
  echo "Wine Mono version: ${WINE_MONO_VERSION}" && \
  mkdir -p /usr/share/wine/mono && \
  wget -nv -O "/usr/share/wine/mono/wine-mono-${WINE_MONO_VERSION}-x86.msi" \
    "https://dl.winehq.org/wine/wine-mono/${WINE_MONO_VERSION}/wine-mono-${WINE_MONO_VERSION}-x86.msi"

RUN \
  mkdir -p /app/OGCS && \
  wget -O /tmp/OGCS.zip \
    "https://github.com/user-attachments/files/22068496/Portable_OGCS_v${OGCS_VERSION}.zip" && \
  7z x /tmp/OGCS.zip -o/app/OGCS && \
  rm /tmp/OGCS.zip

COPY root /

VOLUME /config
EXPOSE 3000