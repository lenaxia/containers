target "docker-metadata-action" {}

variable "VERSION" {
  default = "v0.1.0"
}

variable "SOURCE" {
  default = "https://github.com/lenaxia/containers"
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
    "org.opencontainers.image.title" = "games-on-whales-steam"
    "org.opencontainers.image.description" = "Games on Whales with NVIDIA 595.71.05 graphics-userspace overlay (Talos 595.91.07 GBM regression workaround)"
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
