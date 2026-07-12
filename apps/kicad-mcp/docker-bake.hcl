target "docker-metadata-action" {}

variable "VERSION" {
  // Image version is the kicad-mcp source version (semver of this dir).
  // KiCad version is whatever apt serves as 9.0.* at build time — not tracked here.
  // renovate: datasource=github-releases depName=lenaxia/containers versioning=semver
  default = "0.1.2"
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
    "org.opencontainers.image.title" = "kicad-mcp"
    "org.opencontainers.image.description" = "MCP server bridging LLM agents to KiCad 9 (kicad-cli + kibot + pcbnew)"
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
