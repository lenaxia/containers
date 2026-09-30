#!/usr/bin/env bash
# ai4trade entrypoint — dispatch one of the stack's modes.
#
# The upstream scripts hardcode WS=/workspace/ai4trade as their working
# directory (state files live next to the scripts). In Kubernetes that path
# is a PVC mount, so the read-only copy baked into the image at
# /opt/ai4trade is synced into it on every run; state files already on the
# volume are left untouched.
#
# Usage: entrypoint.sh {daily|scoreboard|heartbeat|ddgate|panel}
set -euo pipefail

MODE="${1:-}"
SRC="${AI4TRADE_SRC:-/opt/ai4trade}"
WS="${AI4TRADE_WORKSPACE:-/workspace/ai4trade}"
CFG_SRC="${AI4TRADE_CONFIG_DIR:-/etc/ai4trade}"

case "${MODE}" in
    daily | scoreboard | heartbeat | ddgate | panel) ;;
    *)
        echo "usage: entrypoint.sh {daily|scoreboard|heartbeat|ddgate|panel}" >&2
        exit 2
        ;;
esac

# --- sync scripts (and optional ConfigMap-provided config) into the state dir
mkdir -p "${WS}/forward"
cp -f \
    "${SRC}/marketdata.py" \
    "${SRC}/trade.py" \
    "${SRC}/control.py" \
    "${SRC}/poll.py" \
    "${SRC}/daily_run.py" \
    "${SRC}/aihf_panel.py" \
    "${SRC}/dd_screen.py" \
    "${SRC}/universe.txt" \
    "${SRC}/personal_sleeve.json" \
    "${WS}/"
cp -f "${SRC}/forward/forward.py" "${WS}/forward/"
if [[ -f "${CFG_SRC}/universe.txt" ]]; then
    cp -f "${CFG_SRC}/universe.txt" "${WS}/universe.txt"
fi
if [[ -f "${CFG_SRC}/personal_sleeve.json" ]]; then
    cp -f "${CFG_SRC}/personal_sleeve.json" "${WS}/personal_sleeve.json"
fi

# --- materialize credentials.json from env (never baked into the image);
#     removed again on exit so nothing persists on the volume
if [[ -n "${AI4TRADE_TOKEN:-}" ]]; then
    python3 - "${WS}/credentials.json" <<'PYEOF'
import json
import os
import sys

creds = {
    "token": os.environ["AI4TRADE_TOKEN"],
    "base_url": os.environ.get("AI4TRADE_BASE_URL", "https://ai4trade.ai/api"),
}
for out_key, env_key in (
    ("openai_api_key", "OPENAI_API_KEY"),
    ("openai_api_base", "OPENAI_API_BASE"),
    ("finnhub_api_key", "FINNHUB_API_KEY"),
):
    if os.environ.get(env_key):
        creds[out_key] = os.environ[env_key]
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(creds, fh, indent=2)
PYEOF
    chmod 600 "${WS}/credentials.json"
    trap 'rm -f "${WS}/credentials.json"' EXIT
fi

case "${MODE}" in
    daily)
        # Full daily workflow (no LLM): marketdata -> trade decision ->
        # execute exits then two-layer-gated entries (dd_verdicts.json veto +
        # headline screen, max 2 trades/day) -> one platform post -> state/log
        python3 "${WS}/daily_run.py"
        ;;
    ddgate)
        # dd_screen.py wraps TradingAgents and needs the TA venv
        # (integration/vendor/TradingAgents). This image does not carry it:
        # the DD gate keeps running workspace-side until a TA-enabled image
        # lands; the k8s CronJob for this mode ships suspended.
        echo "ddgate: requires the TradingAgents image (integration/vendor/TradingAgents venv) — not included here." >&2
        echo "ddgate: the DD gate stays workspace-side until a TA image lands." >&2
        exit 1
        ;;
    scoreboard)
        # Forward-tracker scoreboard AND the control group: replay all OOS
        # variants, then mark the CONTROL buy-and-hold clone to market
        python3 "${WS}/forward/forward.py" && python3 "${WS}/control.py"
        ;;
    heartbeat)
        # Hourly context poller — account summary to last_poll.json
        python3 "${WS}/poll.py"
        ;;
    panel)
        # AIHF panel (stub pending FINANCIAL_DATASETS_API_KEY + mandate)
        python3 "${WS}/aihf_panel.py"
        ;;
esac
