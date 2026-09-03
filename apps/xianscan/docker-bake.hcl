target "docker-metadata-action" {}

variable "VERSION" {
  // renovate: datasource=github-releases depName=ArbenApura/xianscan-rust
  default = "0.5.0-beta.2"
}

variable "SOURCE" {
  default = "https://github.com/ArbenApura/xianscan-rust"
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
  platforms = ["linux/amd64"]
}
