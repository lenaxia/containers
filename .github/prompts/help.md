Post a comment on the issue or PR with the following content (and nothing else):

---

## AI Assistant Commands

The following commands are available in issue and PR comments:

| Command | Description | Custom Text |
|---|---|---|
| `/ai [text]` | General-purpose — context-dependent. On a PR: full re-review. On an issue: analyze and respond. With text: address the specific request. | Optional |
| `/review [text]` | Explicit review of the current PR. Append text to focus on specific areas (rootless, pinning, tests, security). | Optional |
| `/fix <description>` | Fix a specific bug or build failure. Creates a branch, writes structure tests that reproduce the failure, fixes the Dockerfile, opens a PR, iterates through automated review until approved, then merges. | Required |
| `/implement <description>` | Implement a feature or new container image. Reads an existing app for the pattern, writes tests + Dockerfile + docker-bake.hcl, opens a PR, iterates through review until approved. | Required |
| `/test <target>` | Write or improve `tests.yaml` (container-structure-test or goss) for an app. Creates a branch, opens a PR, iterates through review. | Required |
| `/analyze [text]` | Deep read-only analysis of Dockerfiles, build configs, and app architecture. Posts findings as a comment. No code changes. | Optional |
| `/explain <topic>` | Explain container build patterns or app architecture. Posts explanation as a comment. No code changes. | Required |
| `/security [text]` | Security-focused review. Checks rootless execution, secrets in image, package pinning, file permissions, attack surface. Fixes findings if code changes are warranted. | Optional |
| `/triage [text]` | Triage an issue — categorize, prioritize, assess impact, suggest labels and related items. Posts assessment as a comment. | Optional |
| `/design [text]` | Iterate on a design **before** implementing or fixing. Opens a PR, iterates through review until approved, then **holds** — it never auto-merges. | Optional |
| `/merge` | Explicitly merge the current PR (squash, delete branch). Verifies the latest review is APPROVE and required CI is green first. | None |
| `/help` | Show this command reference. | — |

**All commands are available to repository owners, members, and collaborators.**

**Merge control:**
- `/fix`, `/implement`, `/test`, `/security`, and `/design` **follow the
  review-iterate-approve workflow:** branch → PR → automated review → fix → push
  → re-review → repeat until approved.
- `/fix`, `/implement`, `/test`, `/security` **auto-merge** after approval by
  default. Append `--no-merge` to hold the merge until you post `/merge`.
- `/design` **always holds** — design docs never auto-merge; post `/merge` to
  land an approved design.
