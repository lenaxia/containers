target "docker-metadata-action" {}

variable "VERSION" {
  // renovate: datasource=github-releases depName=phw198/OutlookGoogleCalendarSync
  default = "3.0.0.30"
}

variable "SOURCE" {
  default = "https://github.com/phw198/OutlookGoogleCalendarSync"
}

group "default" {
  targets = ["image-local"]
}

target "image" {
  inherits = ["docker-metadata-action"]

  args = {
    VERSION = "${VERSION}"
  }

  labels = {
    "org.opencontainers.image.source" = "${SOURCE}"
  }
}

target "image-local" {
  inherits = ["image"]
  output = ["type=docker"]
}

target "image-all" {
  inherits = ["image"]
  platforms = [
    "linux/amd64",
    "linux/arm64"
  ]
}