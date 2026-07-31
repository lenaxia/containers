You are implementing a feature or new container image for the containers
repository.

**Read README-LLM.md first** — it contains the critical rules.

Rules:
1. Read README-LLM.md before making any changes — it contains hard rules for
   rootless execution, one process per container, pinning, and following existing
   patterns.
2. Read an existing app to learn the pattern before creating a new one. The
   canonical structure is: `Dockerfile`, `docker-bake.hcl`, `tests.yaml`,
   `.dockerignore`, and source (`src/` or scripts). Study `apps/kicad-mcp`
   (Ubuntu + Python MCP server) and `apps/webhook` (Alpine + goss tests) for the
   two common shapes.
3. Test before ship: write `tests.yaml` first — `fileExistenceTests`,
   `commandTests` (container-structure-test) or `process`/`port`/`http` checks
   (goss). Build the image and confirm the tests reflect the intended state.
   Implement the Dockerfile and `docker-bake.hcl`. Rebuild and confirm the tests
   pass.
4. `docker-bake.hcl` must follow the established structure:
   - `target "docker-metadata-action" {}` (inherited by the image target)
   - `variable "VERSION"` with a Renovate annotation and a sensible default
   - `variable "SOURCE"` pointing at the upstream repo
   - `group "default"` → `["image-local"]`
   - `target "image"` (inherits docker-metadata-action, sets args + OCI labels)
   - `target "image-local"` (inherits image, `output = ["type=docker"]`)
   - `target "image-all"` (inherits image, sets platforms)
5. The Dockerfile must:
   - Start with `# syntax=docker/dockerfile:1`
   - Use an Alpine or Ubuntu base — pinned, no `latest`
   - Accept `ARG VERSION` and `ARG TARGETARCH` where appropriate
   - Drop to a non-root `USER` (UID 568 where possible) before the entrypoint
   - Run a single process (lightweight PID-1 reapers like catatonit are
     acceptable; no s6-overlay or supervisord)
   - Pin package versions (`pkg==${VERSION}` for Alpine, explicit versions for
     Ubuntu)
   - Clean up apt/apk caches and `/tmp` to minimize image size
6. Pin everything: base images by sha256 digest where feasible, package versions
   explicit, no `latest` tags.
7. Run `docker buildx bake image-local` and
   `container-structure-test test --image <image> --config tests.yaml` before
   pushing — zero failures required.
8. Leave the repo in a clean buildable state — fix any pre-existing build
   failures you encounter.
