You are explaining container build patterns, layer ordering, or app architecture
in the containers repository. This is a READ-ONLY task — do not make any code
changes.

**Read README-LLM.md first** for the full architectural context (design
principles, app structure, build pipeline).

Rules:
1. Read README-LLM.md for the mission, design principles (rootless, one process,
   pin everything), and app structure conventions.
2. Read the relevant app's `Dockerfile`, `docker-bake.hcl`, and `tests.yaml` as
   needed. Read `Taskfile.yaml` to explain the build/test pipeline.
3. Be clear and specific — reference files, build targets, directives, and data
   flows. Do NOT reference line numbers (they drift).
4. If the explanation reveals issues, note them but do not fix them. Suggest
   `/fix` or `/analyze` for follow-up.
5. Do not create branches, PRs, or make any file changes.
6. Ground every claim in the actual Dockerfile/build config you read — never
   describe build behavior from memory.
