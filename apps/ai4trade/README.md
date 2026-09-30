# ai4trade

Container image for the ai4trade paper-trading stack — a small set of
stdlib-only Python 3 scripts (no pip dependencies) that run as Kubernetes
CronJobs against a paper-trading account. Each container invocation runs
exactly one *mode* and exits.

## Modes

| Mode         | Script                 | What it does                                                                                  |
| ------------ | ---------------------- | --------------------------------------------------------------------------------------------- |
| `daily`      | `control.py`           | Daily mark-to-market of the CONTROL buy-and-hold clone; idempotent per UTC day, self-skips weekends |
| `ddgate`     | `trade.py`             | Drawdown gate / decision engine: checks -5% stop / +15% target exits before entries, market-hours guarded (Mon-Fri 13:30-20:00 UTC) |
| `scoreboard` | `forward/forward.py`  | Forward tracker: refetches daily OHLC, replays all out-of-sample variants, prints comparison JSON |
| `heartbeat`  | `poll.py`              | Hourly account/context poll, writes `last_poll.json`                                          |
| `panel`      | `marketdata.py`        | Full-universe live snapshot (the monthly panel)                                               |

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
