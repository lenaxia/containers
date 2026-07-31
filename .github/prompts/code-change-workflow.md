## Code Change Workflow (MANDATORY)

Every code change MUST follow this review-iterate-approve cycle without
exception:

1. **Read README-LLM.md** — all critical rules apply. Read the target app's
   `Dockerfile`, `docker-bake.hcl`, and `tests.yaml` before implementing. Read an
   existing app (e.g. `apps/kicad-mcp`) before creating a new one to follow the
   established structure (`Dockerfile` + `docker-bake.hcl` + `tests.yaml` +
   `.dockerignore` + `src/`).
2. **Branch:** Create a feature branch (`feat/`, `fix/`, `test/`, `security/`,
   or `docs/` prefix). Never commit to main.
3. **Test before ship:** Write or update `tests.yaml` first. Build the image and
   run the structure tests — they must reflect the new state. Implement the
   Dockerfile/`src/` change. Rebuild and re-run tests — they must pass.
4. **PR:** Open a pull request with a clear description. Reference the triggering
   issue or comment.
5. **Wait for review:** The automated PR review triggers on every PR open and
   push. Wait for it to complete before proceeding.
6. **Address feedback:** Read every finding. Fix ALL real issues. Push to the
   same branch — this triggers automatic re-review.
7. **Iterate:** Repeat steps 5–6 until the automated reviewer posts APPROVE.
8. **Merge:** After approval only — merge with squash method, **unless this run
   was invoked with `--no-merge`** (see Hold below) or it is a `/design` run
   (which always holds).
9. **Report:** Post a comment on the original issue/PR confirming completion with
   a summary of changes.

**Validation required before pushing (zero tolerance):**

```
docker buildx bake image-local
container-structure-test test --image <image> --config tests.yaml
```

Or in one step via Taskfile:

```
task local-build-<app>
```

The build MUST exit 0 and `tests.yaml` MUST show zero failures. Fix pre-existing
failures too — do not ship around them.

**Merge control (`--no-merge` and `/merge`):**
- By default `/fix`, `/implement`, `/test`, and `/security` auto-merge after
  approval (step 8).
- Append `--no-merge` to any of those commands to hold the merge: the run
  iterates to approval but does NOT merge — it stops and waits for an explicit
  `/merge`.
- `/design` **always** holds — design docs never auto-merge.
- `/merge` is the explicit finalize command: it verifies the latest review is
  APPROVE and required CI is green, then squash-merges and deletes the branch.

**Hard rules:**
- NEVER merge before the automated review approves — no exceptions
- NEVER dismiss review findings — fix them or document with evidence why they
  are false alarms
- NEVER commit directly to main
- The image MUST build (`docker buildx bake image-local` exits 0) and
  `tests.yaml` MUST pass — fix pre-existing failures too
- If the review cycle exceeds 3 iterations, step back and reassess the approach —
  something is wrong
