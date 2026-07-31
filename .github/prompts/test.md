You are writing or improving tests for the containers repository.

**Read README-LLM.md first** — test before ship is mandatory.

Rules:
1. Follow the project's testing requirements exactly. Each app's `tests.yaml`
   uses one of two formats — detect it by checking for `schemaVersion` (container-
   structure-test) or its absence (goss):
   - **container-structure-test** (`schemaVersion: 2.0.0`): use
     `fileExistenceTests` (assert binaries, files, dirs exist/don't exist) and
     `commandTests` (run a command inside the image and assert output).
   - **goss**: use `process` (is it running), `port` (is it listening),
     `http` (does it respond), `file` (existence/permissions), and
     `command` (output checks).
2. Cover the meaningful surface of the image, not trivial checks:
   - Does the entrypoint binary/script exist at the expected path?
   - Do installed binaries/tools exist where the Dockerfile places them?
   - Does the app source (`src/` package) import or resolve?
   - For runtime images: does the process start and listen on its port?
   - Does the final user match the `USER` directive (rootless verification)?
3. All tests must pass against a clean build: `docker buildx bake image-local`
   then `container-structure-test test --image <image> --config tests.yaml` (or
   `dgoss run` for goss-based apps).
4. Check existing `tests.yaml` files across apps for patterns and conventions
   before writing new ones. Do not invent novel assertion styles.
5. For new test entries, follow the naming convention used in the target app's
   `tests.yaml` — descriptive `name:` fields that state what is being verified.
6. Never hack tests to pass — if a test fails, fix the root cause (the
   Dockerfile), not the test.
