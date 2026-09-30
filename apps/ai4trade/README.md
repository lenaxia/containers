# ai4trade

Container image for the ai4trade paper-trading stack — a small set of
stdlib-only Python 3 scripts (no pip dependencies) that run as Kubernetes
CronJobs against a paper-trading account. Each container invocation runs
exactly one *mode* and exits.

## Modes

| Mode         | Script(s)                            | What it does                                                                 |
| ------------ | ------------------------------------ | ---------------------------------------------------------------------------- |
| `daily`      | `daily_run.py`                       | Full daily workflow, no LLM: marketdata snapshot -> trade decision -> execute exits then gated entries (DD veto via `dd_verdicts.json`, then headline screen; max 2 trades/day) -> one platform post (biggest mover, alternating `/signals/strategy` / `/discussion`) -> state + log updates. State root is `/data` |
| `ddgate`     | `dd_screen.py`                       | TradingAgents deep-dive on buy candidates (veto-only). **Needs the TA venv** — this image does not carry it; the mode prints a clear error and exits 1. The DD gate runs workspace-side until a TA-enabled image lands (the k8s CronJob ships suspended) |
| `scoreboard` | `forward/forward.py` **and** `control.py` | Forward tracker (refetch, replay OOS variants, comparison JSON), then the CONTROL buy-and-hold clone mark-to-market |
| `heartbeat`  | `poll.py`                            | Hourly account/context poll, writes `last_poll.json`                          |
| `panel`      | `aihf_panel.py`                      | AIHF panel — stub for now (prints a pending note, exit 0) pending `FINANCIAL_DATASETS_API_KEY` + mandate wiring |

`daily_run.py` keeps its state (`state.json`, `log.txt`, `dd_verdicts.json`,
optional `credentials.json` fallback) under `DATA_DIR` (env `AI4TRADE_DATA_DIR`,
default `/data`); the legacy scripts keep theirs under `/workspace/ai4trade`. In
Kubernetes the same PVC is mounted at both paths, so there is one source of
truth. Trades execute via `POST {base}/signals/realtime` (same endpoint/shape as
`deploy_sleeve.py`); the token is never logged.

## Layout

The scripts are baked read-only into `/opt/ai4trade`. The upstream code
hardcodes `/workspace/ai4trade` as its working directory (state files live
next to the scripts), so `entrypoint.sh` syncs the scripts from `/opt/ai4trade`
into `/workspace/ai4trade` on every run — mount a volume there to keep state
(`state.json`, `control_state.json`, `forward/forward_state.json`,
`last_poll.json`, ...) across runs. Files already on the volume that are not
part of the sync set are never touched.

A ConfigMap mounted at `/etc/ai4trade` (keys `universe.txt`,
`personal_sleeve.json`) overrides the baked-in copies when present.

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable              | Required | Description                                                                 |
| --------------------- | -------- | --------------------------------------------------------------------------- |
| `AI4TRADE_TOKEN`      | yes      | Paper-account API token; materialized into `credentials.json` at runtime and wiped on exit |
| `OPENAI_API_KEY`      | no       | Carried into `credentials.json` (integration tooling)                       |
| `OPENAI_API_BASE`     | no       | Carried into `credentials.json` (integration tooling)                       |
| `FINNHUB_API_KEY`     | no       | Carried into `credentials.json` (integration tooling)                       |
| `AI4TRADE_BASE_URL`   | no       | API base URL override (default `https://ai4trade.ai/api`)                   |
| `AI4TRADE_WORKSPACE`  | no       | State dir override (default `/workspace/ai4trade`)                          |

No secrets are baked into the image; `credentials.json` only ever exists at
runtime inside the mounted state directory.

## Usage

```bash
docker run --rm \
    -v ai4trade-state:/workspace/ai4trade \
    -e AI4TRADE_TOKEN=... \
    ghcr.io/lenaxia/ai4trade:1.0.0 heartbeat
```

The Kubernetes CronJobs consuming this image live in the `talos-ops-prod`
repo under `kubernetes/apps/ai4trade/`.
