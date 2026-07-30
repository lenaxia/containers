# README-LLM.md — Project Rules for AI Assistants

This file is the authoritative source for AI workflow rules in this repository.

## Project Overview

**containers** is an opinionated collection of container images. Each app lives
under `apps/<name>/` with a Dockerfile, docker-bake.hcl, tests.yaml, and source.

## Mission

Provide semantically versioned, rootless, multi-architecture container images.
One process per container. Log to stdout. Build on Alpine or Ubuntu. Pin to
sha256 digests.

## Rules

### 0. Test Before You Ship

Every container must pass `tests.yaml` (container-structure-test or goss).
Write/verify tests before modifying a Dockerfile. Verify builds with
`docker buildx bake`.

### 1. Rootless by Default

Containers run as non-root (UID 568 where possible). Never introduce root-only
patterns without explicit justification.

### 2. One Process Per Container

No s6-overlay, supervisord, or init systems. If a service needs a process
manager, that's a sign the architecture is wrong.

### 3. Pin Everything

Base images pinned by sha256 digest. Package versions pinned in Dockerfiles.
No `latest` tags.

### 4. Follow Existing Patterns

Every app follows the same structure: `Dockerfile`, `docker-bake.hcl`,
`tests.yaml`, `.dockerignore`, `src/`. Read an existing app (e.g. `kicad-mcp`)
before creating a new one.

### 5. No Comments Unless Asked

Code and Dockerfiles should be self-documenting. Comments only when strictly
necessary and timeless.

### 6. Neutral, Factual Communication

Do not be sensational or sycophantic. Be a critical collaborator.

### 7. Verify Before Claiming

Never state something exists without showing the file path. Never state
something doesn't exist without showing the grep/search command and empty output.

### 8. No Destructive Git Operations

Never run `git checkout .`, `git reset --hard`, or `git clean -fd`. Multiple
agents may work simultaneously.
