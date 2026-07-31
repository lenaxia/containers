You are iterating on a **design document** for the containers repository — the
step that comes *before* `/implement` or `/fix`. The goal is a reviewed,
approved design, not code.

Output target: a markdown design in the PR description, or an update to the
app's `README.md`, or a design section added to the relevant app directory. There
is no `docs/` design-doc hierarchy in this repo — keep designs close to the code
they describe.

Rules:
1. Read README-LLM.md first — especially the mission and design principles
   (rootless, one process, pin everything, follow existing patterns). Read any
   existing app that touches the same area (e.g. `apps/kicad-mcp`,
   `apps/webhook`) before writing.
2. Decide where the design lives:
   - Small / single-app scope → the PR description itself (markdown).
   - Larger / cross-cutting → a section in the target app's `README.md`, or a
     new design file in the app directory.
   - Updating an existing design → edit it in place; do not silently duplicate.
3. Scope the design to the request text from the collaborator. If the request is
   ambiguous, state the ambiguity explicitly and pick the narrowest reasonable
   scope.
4. A design doc must cover at minimum: problem statement, goals/non-goals,
   proposed design (base image, packages, runtime user, entrypoint, ports,
   volumes), alternatives considered, and open questions. Trace every claim to
   source (file:directive) where the codebase is referenced — do not describe
   behavior from memory.
5. State assumptions up front and validate each one against the actual
   Dockerfile/build config before relying on it.
6. Workflow — follow the Code Change Workflow: feature branch (`design/` or
   `docs/` prefix), open a PR, iterate through the automated review until it
   posts APPROVE.
7. **MERGE HOLD — this command never auto-merges.** After the automated review
   posts APPROVE, STOP. Do not merge. Post a comment on the PR summarising the
   design and stating it is approved and awaiting an explicit `/merge`.
8. Do not write production code in this step — only the design document.
