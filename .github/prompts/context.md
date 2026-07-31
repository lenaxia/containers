Repository: containers — an opinionated collection of container images (`github.com/lenaxia/containers`). Each app lives under `apps/<name>/` with a Dockerfile, docker-bake.hcl, tests.yaml, and source code. Built with Docker Buildx, tested with container-structure-test or goss.

Key directories:
- apps/                    — one directory per container image
- apps/<name>/Dockerfile   — the image build definition
- apps/<name>/docker-bake.hcl — buildx bake config (targets, labels, version)
- apps/<name>/tests.yaml   — container-structure-test or goss tests
- apps/<name>/src/         — source code (Python, Go, shell) copied into the image
- include/                 — shared files (e.g. .dockerignore) rsynced into build context
- Taskfile.yaml            — task runner for local builds and tests

Design principles:
- Rootless (non-root UID 568 where possible)
- One process per container (no s6-overlay, supervisord)
- Log to stdout
- Alpine or Ubuntu base images
- Pin to sha256 digests, never `latest`
- Multi-architecture (amd64 primary)

Authoritative rules:
- README-LLM.md — project rules, conventions, communication guidelines

---

## Before doing anything else: read README-LLM.md at the repo root

It contains the critical guidelines (rootless, one process, pin everything, follow existing patterns, no comments, verify before claiming). Every response must be consistent with it.

---

## Commands

Post a comment on the issue or PR using any of these commands:

- `/ai` — re-assess the current issue or PR in full (issue responder or full PR re-review)
- `/ai <text>` — address a specific request, e.g. `/ai can you also add a health check to the Dockerfile?`
- `/review [text]` — explicit PR code review, optionally focused on a specific area
- `/fix <description>` — fix a bug: branch, tests, PR, iterate through review until approved, merge
- `/implement <description>` — implement a feature: tests, PR, iterate until approved, merge
- `/test <target>` — write or improve tests: PR, iterate until approved, merge
- `/analyze [text]` — deep read-only analysis, posts findings as a comment (no code changes)
- `/explain <topic>` — explain code or architecture, posts explanation as a comment (no code changes)
- `/security [text]` — security-focused review
- `/triage [text>` — triage an issue: categorize, prioritize, suggest labels
- `/design [text]` — iterate on a design document before implementing: opens a PR, iterates through review, **holds for `/merge`** (never auto-merges)
- `/merge` — explicitly merge an approved PR (squash). Use after `/design`, or after `/fix`/`/implement`/`/test`/`/security` invoked with `--no-merge`
- `/help` — show full command reference

Text after the command is appended to the prompt for custom tuning. All code-change commands (`/fix`, `/implement`, `/test`, `/security`) follow the review-iterate-approve-merge workflow: branch → PR → auto-review → fix → push → re-review → repeat until approved → merge. Append `--no-merge` to any of them to hold the merge until you post `/merge`. `/design` always holds.

The assistant will be triggered automatically and will read README-LLM.md and the full thread before responding.
