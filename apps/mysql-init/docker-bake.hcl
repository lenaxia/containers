target "docker-metadata-action" {}

variable "VERSION" {
  // renovate: datasource=repology depName=debian_11/mysql-client versioning=loose
  default = ""
}

variable "SOURCE" {
  default = "https://github.com/mysql/mysql-server"
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
