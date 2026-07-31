You are fixing a bug in the containers repository.

**Read README-LLM.md first** — it contains the critical rules.

Rules:
1. Read README-LLM.md and the target app's `Dockerfile`, `docker-bake.hcl`, and
   `tests.yaml` before making any changes.
2. Identify the root cause — do not fix symptoms. Trace the actual build,
   `RUN`/`COPY`/`USER` directives, and `tests.yaml` assertions to confirm where
   the defect lives.
3. Test before ship (TDD for containers): write or update a `tests.yaml` test
   case that reproduces the failure, build the image, and confirm the test fails.
   Then implement the fix, rebuild, and confirm the test passes.
4. **Regression tests are mandatory, not optional.** For every bug you fix, write
   a structure test (container-structure-test `fileExistenceTests` /
   `commandTests`, or goss checks) that:
   - Would FAIL against the old (broken) image and PASS against the fixed image.
   - Targets the specific defect, not just the general feature area — name it
     after the bug (e.g. `Fix_WrongUserOwnership`, `Fix_MissingEntrypoint`).
   - Covers the exact path/binary/behavior that triggered the bug plus adjacent
     edge cases the same build step could hit.
   - Is committed alongside the fix in the same PR, never as a follow-up.
   A `/fix` PR that ships a Dockerfile change without a structure test for the
   bug it addresses is incomplete and must not be merged. If you discover
   additional bugs while fixing the reported one, write a test for each before
   fixing it.
5. Containers run rootless (non-root UID 568 where possible). One process per
   container — no s6-overlay.
6. Pin everything: package versions explicit, no `latest` tags.
7. Run `docker buildx bake image-local` and
   `container-structure-test test --image <image> --config tests.yaml` before
   pushing — zero failures required.
8. If the fix touches multiple layers (base image → package install → runtime
   user → entrypoint), ensure structure tests cover each layer.
