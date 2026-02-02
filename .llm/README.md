# AI Workflows for Container Images Repository

This document describes the AI-powered workflows implemented in this repository to automate issue triage, PR reviews, and failure analysis.

## Overview

This repository uses [OpenCode](https://opencode.ai) to power three main AI workflows:

1. **Issue Responder** - Automatically triages new issues, adds labels, and provides helpful responses
2. **Renovate Reviewer** - Reviews Renovate bot PRs for dependency updates and assesses risk
3. **Failure Analysis** - Analyzes failed CI/CD workflows and creates/updates issues with root cause analysis

## Prerequisites

### Required Secrets

To use these workflows, you need to set up the following GitHub secrets:

- `OPENAI_API_KEY` - Your OpenAI API key (or compatible API key for local LLM)
- `OPENAI_API_BASE` - The API base URL (e.g., `https://api.openai.com/v1` for OpenAI, or your local LLM endpoint)
- `OPENAI_MODEL` - The model to use (e.g., `gpt-4`, `claude-sonnet-4`, or your local model name)

The `GITHUB_TOKEN` is automatically provided by GitHub Actions.

### Optional Notification Secrets

All workflows support optional notifications via Slack and Pushover:

**Slack Notifications:**
- `SLACK_WEBHOOK_URL` - Your Slack incoming webhook URL (get one at https://api.slack.com/messaging/webhooks)

**Pushover Notifications:**
- `PUSHOVER_USER_KEY` - Your Pushover user key
- `PUSHOVER_API_TOKEN` - Your Pushover application API token (get these at https://pushover.net)

Notifications will automatically be sent when:
- **Issue Responder**: A new issue is triaged (includes labels and priority)
- **Renovate Reviewer**: A Renovate PR is reviewed (indicates auto-merge vs manual review)
- **Failure Analysis**: A workflow fails (includes link to issue and workflow run)

### Using with Local LLMs

These workflows are designed to work with local LLMs by setting the `OPENAI_API_BASE` to your local endpoint (e.g., `http://your-llm-server:8000/v1`). The OpenCode CLI respects these environment variables and will route requests to your specified endpoint.

## Workflows

### 1. Issue Responder (`.github/workflows/issue-responder.yml`)

**Trigger:** When a new issue is opened

**What it does:**
- Analyzes the issue content to determine type (bug, feature, question, documentation)
- Identifies which container image the issue relates to
- Checks if the issue has sufficient information
- Adds appropriate labels:
  - Type: `bug`, `enhancement`, `question`, `documentation`
  - Priority: `P0`, `P1`, `P2`, `P3`
  - Container-specific: `app/[container-name]`
- Posts a comment:
  - Welcomes the user
  - Requests missing information if needed
  - Provides immediate guidance for straightforward issues
  - Mentions similar/duplicate issues if found

**Permissions:**
- `contents: read`
- `issues: write`

**Model:** Configurable via `OPENAI_MODEL` secret

### 2. Renovate Reviewer (`.github/workflows/renovate-review.yml`)

**Trigger:** When Renovate bot opens or updates a PR

**What it does:**
- Analyzes the dependency updates in the PR
- Reviews changes to:
  - Base images (Alpine, Ubuntu)
  - Application versions
  - GitHub Actions versions
  - Other dependencies
- Assesses risk level:
  - **LOW**: Patch updates, security fixes → Can auto-merge
  - **MEDIUM**: Minor updates with backward compatibility → Review recommended
  - **HIGH**: Major updates, base image changes → Manual review required
- Posts a review comment with:
  - Summary of updates
  - Risk assessment
  - Concerns or items needing verification
  - Recommendation (auto-merge vs manual review)
- For LOW risk: Adds `automerge` label and approves
- For MEDIUM/HIGH risk: Adds `review-required` label

**Permissions:**
- `contents: read`
- `pull-requests: write`

**Model:** Configurable via `OPENAI_MODEL` secret

### 3. Failure Analysis (`.github/workflows/failure-analysis.yml`)

**Trigger:** When "Build Apps", "Release", or "Retry Release" workflows fail

**What it does:**
- Fetches failed workflow logs
- Analyzes the failure to determine:
  - Root cause
  - Which container(s) or job(s) failed
  - Error messages and stack traces
  - Whether issue is transient or persistent
- Categorizes failures:
  - **TRANSIENT**: Network issues, timeouts (likely to succeed on retry)
  - **DEPENDENCY**: Upstream package/image issues
  - **CODE**: Issues with Dockerfiles or build scripts
  - **INFRA**: GitHub Actions infrastructure issues
  - **UNKNOWN**: Cannot determine from logs
- Assigns severity: `P0` (critical) through `P3` (low)
- Checks for existing open issues for this workflow
- Takes appropriate action:
  - If issue exists: Adds comment with new failure details and pattern analysis
  - If no issue: Creates new issue with root cause, error excerpts, and suggested fixes
- Adds labels: `ci-failure`, `workflow:[name]`, severity

**Permissions:**
- `contents: read`
- `actions: read`
- `issues: write`

**Model:** Configurable via `OPENAI_MODEL` secret

## Security & Permissions

All workflows use OpenCode CLI which can be configured with fine-grained permissions. By default, these workflows allow:
- GitHub CLI (`gh`) commands for managing issues, labels, and comments
- Read-only file operations
- Repository inspection
- Git commands for history analysis

The AI cannot execute destructive commands, ensuring safe automation.

## Notifications

All workflows include optional notification support via Slack and Pushover. Notifications are sent automatically when workflows complete.

### Slack Integration

To enable Slack notifications:

1. Create an incoming webhook in your Slack workspace:
   - Go to https://api.slack.com/messaging/webhooks
   - Create a new webhook for your desired channel
   - Copy the webhook URL

2. Add the webhook URL as a GitHub secret:
   - Repository Settings → Secrets and variables → Actions
   - New repository secret: `SLACK_WEBHOOK_URL`

**Notification Format:**

- **Issue Responder**: Sends a formatted message with issue details, labels, and direct link
- **Renovate Reviewer**: Color-coded based on risk level (green for auto-merge, orange for manual review)
- **Failure Analysis**: Red alert with links to both the failed workflow run and the created/updated issue

### Pushover Integration

To enable Pushover notifications:

1. Sign up at https://pushover.net and create an application
2. Note your User Key and Application API Token

3. Add both as GitHub secrets:
   - `PUSHOVER_USER_KEY` - Your user key
   - `PUSHOVER_API_TOKEN` - Your application API token

**Notification Priorities:**

- **Issue Responder**: Priority mapped from issue labels (P0 = Emergency, P1 = High, P2 = Normal, P3 = Low)
- **Renovate Reviewer**: High priority for manual review required, Low priority for auto-merge approved
- **Failure Analysis**: High priority for all failures (recurring failures emphasized)

### Disabling Notifications

Notifications are optional. If the secrets are not set, workflows will skip the notification steps without errors.

## Customization

### Adjusting AI Behavior

You can customize the AI's behavior by editing the prompts in each workflow file. Key areas to customize:

1. **Issue Responder:**
   - Label naming conventions
   - Response tone and style
   - Information required for different issue types

2. **Renovate Reviewer:**
   - Risk thresholds for auto-merge
   - Specific checks for your container types
   - Custom merge criteria

3. **Failure Analysis:**
   - Failure categories specific to your builds
   - Severity classification rules
   - Issue template format

### Changing AI Models

The model is configured via the `OPENAI_MODEL` GitHub secret. You can use:

- **OpenAI Models:** `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- **Anthropic Models (via compatible API):** `claude-sonnet-4`, `claude-opus-4`, `claude-haiku-4`
- **Local LLMs:** Any model supported by your local LLM server (e.g., `llama-3`, `mistral`, etc.)

Update the `OPENAI_MODEL` secret in your repository settings.

## Testing

Before enabling these workflows in production:

1. Test each workflow using `workflow_dispatch` trigger (add to workflow)
2. Review the AI outputs in a test repository
3. Adjust prompts based on the quality of responses
4. Monitor costs and rate limits

## Cost Considerations

- Issue Responder: ~1-2k tokens per issue
- Renovate Reviewer: ~2-5k tokens per PR (depends on diff size)
- Failure Analysis: ~5-10k tokens per failure (depends on log size)

**For OpenAI API:** Monitor usage in your OpenAI dashboard.
**For Local LLMs:** Costs are primarily compute/hosting, with no per-token charges.

## Troubleshooting

### Workflow doesn't trigger
- Check that `OPENAI_API_KEY`, `OPENAI_API_BASE`, and `OPENAI_MODEL` secrets are set correctly
- For local LLMs, verify the API endpoint is accessible from GitHub Actions runners
- Verify workflow permissions in repository settings
- Check workflow run logs for errors

### AI produces unhelpful responses
- Review and refine the prompts
- Consider using a more capable model
- Provide more context in the prompt about your repository

### Rate limiting
- Reduce the number of workflows or triggers
- Use a less expensive model for simple tasks
- Implement caching where possible

## Resources

- [OpenCode Documentation](https://opencode.ai/docs)
- [OpenCode GitHub](https://github.com/anomalyco/opencode)
- [Comprehensive AI Workflows Guide](.llm/AI_WORKFLOWS_GUIDE.md)

## Support

For issues with:
- **These workflows:** Open an issue in this repository
- **OpenCode itself:** Visit https://github.com/anomalyco/opencode
- **General AI workflow patterns:** See the comprehensive guide at `.llm/AI_WORKFLOWS_GUIDE.md`
