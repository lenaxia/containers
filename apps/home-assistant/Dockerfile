# syntax=docker/dockerfile:1

ARG TARGETARCH
ARG ARCH=${TARGETARCH/arm64/aarch64}
FROM ghcr.io/home-assistant/${ARCH}-base-python:3.13-alpine3.21
ARG TARGETARCH
ARG ARCH=${TARGETARCH/arm64/aarch64}
ARG VERSION

ENV \
    CRYPTOGRAPHY_DONT_BUILD_RUST=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=true \
    UV_SYSTEM_PYTHON=true

ENV HOME="/config" \
    PYTHONUSERBASE="/usr/local" \
    VENV_FOLDER="/config/.venv"

USER root
WORKDIR /app

# Install system dependencies
RUN apk add --no-cache \
        bash \
        binutils \
        bluez \
        bluez-deprecated \
        bluez-libs \
        ca-certificates \
        catatonit \
        coreutils \
        cups-libs \
        curl \
        eudev-libs \
        ffmpeg \
        git \
        grep \
        hwdata-usb \
        imlib2 \
        iperf3 \
        iputils \
        jq \
        libcap \
        libftdi1 \
        libgpiod \
        libturbojpeg \
        libpulse \
        libstdc++ \
        libxslt \
        libzbar \
        mailcap \
        mariadb-connector-c \
        nano \
        net-tools \
        nmap \
        openssh-client \
        openssl \
        pianobar \
        postgresql-libs \
        pulseaudio-alsa \
        socat \
        tiff \
        tzdata \
        unzip \
        xz

# Install build dependencies
RUN apk add --no-cache --virtual=.build-deps \
        autoconf \
        build-base \
        libffi-dev

# Install uv package manager
RUN pip install uv

# Create temporary directory for downloads
RUN mkdir -p /tmp/homeassistant

# Download and extract Home Assistant core
RUN if [ -z "$VERSION" ]; then \
        echo "ERROR: VERSION argument is not set" && exit 1; \
    fi && \
    echo "Downloading Home Assistant version: $VERSION" && \
    curl -fsSL "https://github.com/home-assistant/core/archive/${VERSION}.tar.gz" \
        | tar xzf - -C /tmp/homeassistant --strip-components=1 || \
    (echo "Failed to download Home Assistant core version ${VERSION}" && exit 1)

# Get Home Assistant base version
RUN HOME_ASSISTANT_BASE=$(curl -fsSL "https://raw.githubusercontent.com/home-assistant/core/${VERSION}/build.yaml" | grep "${ARCH}: " | cut -d ":" -f3) && \
    echo "Home Assistant base version: $HOME_ASSISTANT_BASE" && \
    if [ -z "$HOME_ASSISTANT_BASE" ]; then \
        echo "ERROR: Failed to determine Home Assistant base version" && exit 1; \
    fi && \
    echo $HOME_ASSISTANT_BASE > /tmp/home_assistant_base

# Install Home Assistant requirements
RUN HOME_ASSISTANT_BASE=$(cat /tmp/home_assistant_base) && \
    uv pip install --only-binary=:all: --find-links "https://wheels.home-assistant.io/musllinux/" \
        --requirement "https://raw.githubusercontent.com/home-assistant/docker/${HOME_ASSISTANT_BASE}/requirements.txt"

# Install all requirements
RUN if [ ! -f /tmp/homeassistant/requirements_all.txt ]; then \
        echo "ERROR: requirements_all.txt not found" && exit 1; \
    fi && \
    uv pip install --only-binary=:all: --find-links "https://wheels.home-assistant.io/musllinux/" \
        --requirement /tmp/homeassistant/requirements_all.txt

# Install Home Assistant
RUN uv pip install --only-binary=:all: --find-links "https://wheels.home-assistant.io/musllinux/" \
        homeassistant=="${VERSION}"

# Install additional dependencies
RUN uv pip install ldap3 rpds-py

# Install tiktoken from pre-compiled wheel
RUN uv pip install --only-binary=:all: \
        --find-links "https://wheels.home-assistant.io/musllinux/" \
        --find-links "https://pypi.org/simple/" \
        tiktoken

# Install all strands packages with pip to ensure consistent versioning
RUN pip install --no-cache-dir --index-url https://pypi.org/simple/ \
        strands-agents==0.2.1 \
        'strands-agents[litellm]==0.2.1' \
        strands-agents-tools \
        strands-agents-builder

# Install other CortexAgent dependencies with uv
RUN uv pip install \
        pydantic>=2.0.0 \
        boto3 \
        anthropic>=0.52.0 \
        mcp \
        anyio>=4.9.0 \
        aiohttp_sse>=2.2.0 \
        voluptuous

# Install go2rtc
RUN curl -fsSL -o /bin/go2rtc \
        "https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_${TARGETARCH}" && \
    chmod +x /bin/go2rtc && \
    mkdir -p /config && \
    chown nobody:nogroup -R /config

# Clean up
RUN apk del --purge .build-deps && \
    rm -rf /root/.cache /root/.cargo /tmp/*

COPY . /

USER nobody:nogroup
WORKDIR /config
VOLUME ["/config"]

ENTRYPOINT ["/usr/bin/catatonit", "--", "/entrypoint.sh"]

