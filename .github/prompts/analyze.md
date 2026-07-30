You are performing a deep analysis of the containers repository. This is a
READ-ONLY task — do not make any code changes.

**Read README-LLM.md first** for full context on the design principles
(rootless, one process, pin everything, follow existing patterns).

Rules:
1. Read README-LLM.md for the mission, design principles, and critical rules.
2. Read the target app's `Dockerfile`, `docker-bake.hcl`, `tests.yaml`, and
   `src/` as needed. Read the `Taskfile.yaml` to understand the build/test
   pipeline.
3. Be specific — reference file paths, target names, directive names, and build
   steps. Do NOT reference line numbers (they drift).
4. If you find bugs, build flaws, or design weaknesses, describe them precisely
   with reproduction steps (the exact `docker buildx bake` /
   `container-structure-test` commands that would expose them) or Dockerfile
   references.
5. Do not create branches, PRs, or make any file changes.
6. If the analysis reveals issues that should be fixed, suggest using `/fix` or
   `/implement` in your response.

Output format:
## Analysis

### Topic
[What was analyzed]

### Findings
[Detailed findings with file path references]

### Recommendations
[Suggested actions, if any — reference appropriate commands like `/fix` or `/implement`]
