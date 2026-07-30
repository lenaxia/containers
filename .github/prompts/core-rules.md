## Core Rules

These rules apply to every response. They are non-negotiable. They are
summarized here for the AI workflow; the authoritative source is README-LLM.md
(read it in full before making changes).

### 1. Test Before You Ship

Every container must pass `tests.yaml` (container-structure-test or goss) and
build cleanly with `docker buildx bake`. Write or verify tests before modifying
a Dockerfile.

1. Build the image: `docker buildx bake image-local`
2. Run structure tests: `container-structure-test test --image <image> --config tests.yaml`
3. Verify both pass before opening a PR

Full local validation (build + test in one step):

```
task local-build-<app>
```

A Dockerfile change that does not build or whose `tests.yaml` does not pass is
incomplete and must not be merged.

### 2. Assumptions: State, Then Validate

Every non-trivial claim rests on assumptions. Unstated, unvalidated assumptions
cause most bugs.

**Mandatory protocol:**

- State every assumption explicitly before relying on it.
- Validate every assumption — read the Dockerfile, run a build, check
  `docker-bake.hcl`, inspect `tests.yaml`, or query the image. Do not proceed on
  an assumption you have not verified.
- If you cannot validate an assumption, do not rely on it. Redesign so it is
  unnecessary, or ask the user.
- Record what proved each assumption (file path, build output, test name).

**Red flag words — these signal an unvalidated assumption. When you catch
yourself using them, stop and verify:**

- "probably", "likely", "should be", "should work", "I believe", "I assume",
  "appears to", "seems like", "I think", "presumably", "in theory", "ought to",
  "most likely", "chances are", "it's safe to assume", "I'm fairly confident",
  "as expected", "the expectation is", "normally", "typically", "by convention",
  "standard practice is", "the intent is", "this is meant to", "designed to",
  "supposed to"

When any of these appear in your reasoning or output, replace them with verified
evidence or explicitly flag them as unvalidated assumptions that need proof.

**Never claim what the Dockerfile or image does without reading it.** Do not
describe behavior from memory, convention, or inference. Read the actual
Dockerfile, trace the actual `RUN`/`COPY`/`USER` directives, confirm the actual
behavior. "I haven't verified this" is an honest answer. An unverified claim
presented as fact is worse.

### 3. Rootless by Default

Containers run as non-root (UID 568 where possible). Never introduce root-only
patterns without explicit justification. The final `USER` directive must drop to
a non-root user.

### 4. One Process Per Container

No s6-overlay, supervisord, or init systems. If a service needs a process
manager, that's a sign the architecture is wrong. Lightweight PID-1 reapers
(catatonit) are acceptable; multi-service orchestration is not.

### 5. Pin Everything

Base images pinned by sha256 digest where feasible. Package versions pinned in
Dockerfiles (`pkg==${VERSION}` for Alpine, explicit versions for Ubuntu). No
`latest` tags. Version variables in `docker-bake.hcl` carry Renovate annotations
so updates are tracked.

### 6. Follow Existing Patterns

Every app follows the same structure: `Dockerfile`, `docker-bake.hcl`,
`tests.yaml`, `.dockerignore`, and source (`src/` or scripts). Read an existing
app (e.g. `apps/kicad-mcp`) before creating a new one. Do not invent a novel
layout.

### 7. No Comments Unless Asked

Dockerfiles and code should be self-documenting. Comments only when strictly
necessary and timeless.

### 8. Neutral, Factual Communication

Do not be sensational or sycophantic. Be a critical collaborator. State findings
directly.

### 9. Verify Before Claiming

Never state something exists without showing the file path. Never state something
doesn't exist without showing the grep/search command and empty output.

### 10. No Destructive Git Operations

Never run `git checkout .`, `git reset --hard`, or `git clean -fd`. Multiple
agents may work simultaneously.

### Zero Technical Debt

- No TODOs, FIXMEs, or commented-out code
- No adapters for backwards compatibility — implement the final solution
- Never hack tests to pass — fix the root cause
- Pre-existing build failures are not acceptable — fix them when encountered
