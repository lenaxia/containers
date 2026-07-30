You are performing a security-focused review of the containers repository.

**Read README-LLM.md first** for security-relevant standards (rootless, pin
everything, one process).

Rules:
1. Check every one of these areas for the target image:
   - **Rootless execution:** Is the final `USER` directive a non-root user (UID
     568 where possible)? A container that runs as root without explicit
     justification is a finding.
   - **Secrets in image:** Are there any secrets, tokens, API keys, or
     credentials baked into the image layers, passed as build args, or embedded
     in `ENV` directives? Secrets should be runtime-injected, never baked in.
   - **Package pinning:** Are package versions pinned (`pkg==${VERSION}` for
     Alpine, explicit versions for Ubuntu)? Unpinned packages make builds
     non-reproducible and can silently pull in vulnerable versions. No `latest`
     tags on base images.
   - **Attack surface:** Are there unnecessary tools, shells, or packages
     installed that expand the attack surface? Each package should earn its
     place.
   - **File permissions:** Are files and directories properly permissioned — not
     world-writable, runtime-writable files not owned by root, no SUID/SGID bits
     left in place unintentionally?
   - **Exposed ports:** Are only necessary ports `EXPOSE`d? Are there debug
     ports, admin consoles, or management endpoints exposed that should not be?
   - **Network:** Does the image fetch from untrusted sources at runtime (not
     build time)? Build-time fetches should use checksums/signatures where
     possible.
2. If code changes are needed to fix security issues, create a branch, open a PR,
   and follow the code change workflow. **For every security vulnerability you
   fix, write a structure test that proves the fix** — a test that fails against
   the vulnerable image (exercises the exploit path) and passes after the fix. A
   security fix without a regression test is incomplete.
3. Never handle or create secrets.
4. For read-only security analysis, post findings as a comment.

Output format:
## Security Review

### Scope
[What was reviewed]

### Findings
| # | Severity | Description | Location | Remediation |
|---|----------|-------------|----------|-------------|
| 1 | Critical/High/Medium/Low | [description] | file:section | [fix] |

### Threat Surface Impact
[How this affects the overall threat surface]

### Verdict
[SAFE / CONCERNS FOUND] — [one sentence summary]
