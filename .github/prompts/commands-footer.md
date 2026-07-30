## AI Assistant Commands

The following commands are available on this issue/PR thread. Reply with one to
trigger the assistant — any text after a command tunes the request (e.g.
`/review focus on the rootless USER directive`).

| Command | Description |
|---|---|
| `/ai [text]` | Re-assess this issue/PR in full, or address a specific request (context-dependent). |
| `/review [text]` | Explicit review of the current PR. Append text to focus on specific areas (rootless, pinning, tests, security). |
| `/fix <description>` | Fix a bug: creates a branch, writes structure tests that reproduce the failure, fixes the Dockerfile/build, opens a PR, iterates through review until approved, then merges. |
| `/implement <description>` | Implement a feature or new container image: reads an existing app for the pattern, writes tests + Dockerfile + docker-bake.hcl, opens a PR, iterates through review until approved, then merges. |
| `/test <target>` | Write or improve `tests.yaml` (container-structure-test or goss) for the specified app. Opens a PR, iterates through review until approved. |
| `/analyze [text]` | Deep read-only analysis of Dockerfiles, build configs, and app architecture. Posts findings as a comment. No code changes. |
| `/explain <topic>` | Explain container build patterns, layer ordering, or app architecture. Posts explanation as a comment. No code changes. |
| `/security [text]` | Security-focused review (rootless execution, secrets in image, package pinning, file permissions, attack surface). |
| `/triage [text]` | Triage an issue — categorize, prioritize, assess impact, suggest labels. |
| `/design [text]` | Iterate on a design before implementing. Opens a PR, iterates through review, then **holds** (never auto-merges). |
| `/merge` | Explicitly merge an approved PR (squash). Use after `/design` or a `--no-merge` run. |
| `/help` | Show the full command reference. |

**All commands are available to repository owners, members, and collaborators.**
Code-change commands (`/fix`, `/implement`, `/test`, `/security`) auto-merge
after approval by default — append `--no-merge` to hold for an explicit
`/merge`. `/design` always holds. None of these ever commit to `main` directly.
