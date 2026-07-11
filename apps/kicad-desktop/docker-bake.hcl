target "docker-metadata-action" {}

variable "VERSION" {
  // Selkies base image is tagged by branch (main) + Ubuntu release.
  // KiCad version is whatever the apt repo serves as 9.0.* on build day.
  // Renovate updates the base image digest via the dockerDatasource below.
  // renovate: datasource=docker depName=ghcr.io/selkies-project/selkies-gstreamer/gst-py-example versioning=loose
  default = "main-ubuntu24.04"
}

variable "SOURCE" {
  default = "https://github.com/selkies-project/selkies-gstreamer"
}

group "default" {
  targets = ["image-local"]
}

target "image" {
  inherits = ["docker-metadata-action"]
  args = {
    VERSION = "${VERSION}"
    VENDOR = "${VENDOR}"
  }
  labels = {
    "org.opencontainers.image.source" = "${SOURCE}"
    "org.opencontainers.image.title" = "kicad-desktop"
    "org.opencontainers.image.description" = "KiCad 9 streaming workstation (Selkies + Sunshine + Intel VAAPI)"
  }
}

target "image-local" {
  inherits = ["image"]
  output = ["type=docker"]
}

# KiCad 9 apt repo publishes amd64 only, and the Selkies base image is
# amd64-only. Force a single platform to keep bake from trying to build arm64
# (which would fail at apt-get install kicad).
target "image-all" {
  inherits = ["image"]
  platforms = ["linux/amd64"]
}
