target "docker-metadata-action" {}

variable "VERSION" {
  default = "0.1.0"
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
    "org.opencontainers.image.title" = "opengist-mcp"
    "org.opencontainers.image.description" = "MCP server bridging LLM agents to Opengist"
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
