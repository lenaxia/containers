#!/usr/bin/env bash
version=$(curl -s https://pkgs.alpinelinux.org/package/edge/community/x86_64/transmission | grep -oP 'transmission-\K[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -n 1)
version="${version%%_*}"
version="${version%%-*}"
printf "%s" "${version}"
