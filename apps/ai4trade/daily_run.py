#!/usr/bin/env python3
"""Daily runner for the ai4trade paper-trading stack — executes, without any
LLM, the workflow the workspace agent performs manually.

Steps per run (all state under DATA_DIR, default /data — the PVC mount; the
same volume is also mounted at /workspace/ai4trade for the upstream scripts):
  1) marketdata.py snapshot (subprocess, stdout JSON)
  2) trade.py decision (subprocess, stdout JSON — exits before entries; it
     never trades itself)
  3) execute exits first, then two-layer-gated entries:
       layer 1  DD gate — DATA_DIR/dd_verdicts.json dated today with verdict
                "veto" for the symbol -> skip the buy (DD_VETO). Missing or
                stale file = no vetoes (abstain never blocks).
       layer 2  headline screen on the entry's own headlines — skip on
                material political / regulatory / earnings risk, and on
                unavailable headlines (SKIP_BUY)
       max 2 executed trades per UTC day (state "trades_YYYYMMDD" counter)
  4) publish at most one platform post per UTC day (content built from the
     snapshot's biggest mover — cited prices + falsification level, no hype),
     alternating POST {base}/signals/strategy and {base}/discussion on
     state.post_count parity
  5) update DATA_DIR/state.json and append DATA_DIR/log.txt
     (DAILY / TRADED / SKIP_BUY / DD_VETO lines, workspace log format)

Credentials: AI4TRADE_TOKEN env, falling back to DATA_DIR/credentials.json.
Trades go through POST {base}/signals/realtime (same endpoint and body shape
as deploy_sleeve.py). The token is never logged.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

WS = os.environ.get("AI4TRADE_WORKSPACE", "/workspace/ai4trade")
DATA_DIR = os.environ.get("AI4TRADE_DATA_DIR", "/data")
BASE = os.environ.get("AI4TRADE_BASE_URL", "https://ai4trade.ai/api").rstrip("/")
MAX_TRADES_PER_DAY = 2

RISK_PAT = re.compile(
    r"(lawsuit|indict\w*|fraud|probe|investigat\w*|\bsec\b|\bdoj\b|sanction\w*|"
    r"recall\w*|bankrupt\w*|resign\w*|downgrade\w*|halted|guidance (?:cut|lower\w*)|"
    r"miss(?:es|ed)? (?:earnings|estimates|revenue)|layoff\w*|delist\w*|ceo exit)", re.I)


def log(tag, line):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(DATA_DIR, "log.txt"), "a") as fh:
        fh.write("%s %s %s\n" % (ts, tag, line))


def creds():
    tok = os.environ.get("AI4TRADE_TOKEN", "")
    if tok:
        return {"token": tok, "base_url": BASE}
    try:
        with open(os.path.join(DATA_DIR, "credentials.json")) as fh:
            c = json.load(fh)
        c.setdefault("base_url", BASE)
        return c
    except Exception:
        return None


def api(c, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(c["base_url"].rstrip("/") + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + c["token"])
    req.add_header("X-Claw-Token", c["token"])
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return {"_error": "HTTP %s %s" % (e.code, e.read().decode()[:200])}
    except Exception as e:
        return {"_error": str(e)[:200]}


def dd_vetoes(today):
    """Veto-only DD gate: {symbol: verdict-row} for TODAY's file only."""
    try:
        with open(os.path.join(DATA_DIR, "dd_verdicts.json")) as fh:
            v = json.load(fh)
    except Exception:
        return {}
    if v.get("date") != today:
        return {}
    return {r.get("symbol"): r for r in v.get("verdicts", []) if r.get("verdict") == "veto"}


def headline_risk(headlines):
    """Layer 2: conservative screen of the entry's own headlines."""
    if not headlines or any(not h.strip() or h.startswith("_news_fetch_error") for h in headlines):
        return "headline screen unavailable"
    for h in headlines:
        if RISK_PAT.search(h):
            return "risk headline: %s" % h[:120]
    return None


def biggest_mover(snap):
    stocks = [s for s in snap.get("stocks", []) if isinstance(s, dict) and "error" not in s and s.get("sym")]
    return max(stocks, key=lambda s: abs(s.get("chg_1d_pct") or 0.0)) if stocks else None


def post_content(mover, snap):
    sym, chg, px = mover["sym"], mover.get("chg_1d_pct") or 0.0, mover.get("price") or 0.0
    hi, lo = mover.get("week_52_high"), mover.get("week_52_low")
    levels = []
    if hi:
        levels.append("52w high $%.2f" % hi)
    if lo:
        levels.append("52w low $%.2f" % lo)
    ref = " (%s)" % ", ".join(levels) if levels else ""
    return (
        "%s moved %+.2f%% on the day, last $%.2f%s (platform marketdata snapshot %s). "
        "Record-keeping post, not a recommendation. Falsification: the momentum read is "
        "wrong if %s closes below today's $%.2f within 5 sessions or the 1-day change "
        "flips negative; the benchmark-relative claim fails if 1d RS vs SPY turns "
        "negative. Levels cited from the snapshot above; no targets, no hype."
        % (sym, chg, px, ref, snap.get("fetched_at_utc", "n/a"), sym, px))


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    os.makedirs(DATA_DIR, exist_ok=True)
    state = {}
    try:
        with open(os.path.join(DATA_DIR, "state.json")) as fh:
            state = json.load(fh)
    except Exception:
        pass
    tkey = "trades_" + today
    trades_today = int(state.get(tkey) or 0)

    snap = json.loads(subprocess.run(
        [sys.executable, WS + "/marketdata.py"], capture_output=True, text=True,
        timeout=180, cwd=WS).stdout)
    log("DAILY", "data_snapshot %s" % ",".join(
        s.get("sym", "?") for s in snap.get("stocks", []) if isinstance(s, dict)))

    decision = json.loads(subprocess.run(
        [sys.executable, WS + "/trade.py"], capture_output=True, text=True,
        timeout=300, cwd=WS).stdout)
    if not decision.get("ok"):
        print(json.dumps({"ok": False, "error": "trade decision failed",
                          "detail": str(decision.get("error"))[:200]}))
        sys.exit(1)

    c = creds()
    if not c:
        print(json.dumps({"ok": False, "error": "no credentials (AI4TRADE_TOKEN or %s/credentials.json)"
                          % DATA_DIR}))
        sys.exit(1)
    vetoes = dd_vetoes(today)
    executed = []

    def trade(action, sym, qty, reason):
        resp = api(c, "POST", "/signals/realtime",
                   {"market": "us-stock", "action": action, "symbol": sym, "price": 0,
                    "quantity": qty, "executed_at": "now", "content": reason})
        if "_error" in resp:
            log("TRADE_ERROR", "%s %s x%s (%s)" % (action, sym, qty, resp["_error"]))
            return False
        log("TRADED", "%s %s x%s %s" % (action, sym, qty, reason))
        return True

    for e in decision.get("exits", []):
        if trades_today >= MAX_TRADES_PER_DAY:
            break
        if trade("sell", e["symbol"], e["quantity"], e["reason"]):
            executed.append(e["symbol"])
            trades_today += 1

    for ent in decision.get("entries", []):
        sym = ent.get("symbol")
        if trades_today >= MAX_TRADES_PER_DAY:
            log("SKIP_BUY", "%s max %d trades/day reached" % (sym, MAX_TRADES_PER_DAY))
            break
        if not decision.get("market_open"):
            log("SKIP_BUY", "%s market closed (execute only 13:30-20:00 UTC weekdays)" % sym)
            continue
        if sym in vetoes:
            log("DD_VETO", "%s %s" % (sym, (vetoes[sym].get("thesis_excerpt") or "")[:120]))
            continue
        risk = headline_risk(ent.get("headlines") or [])
        if risk:
            log("SKIP_BUY", "%s %s" % (sym, risk))
            continue
        if trade("buy", sym, ent.get("quantity", 0), ent.get("reason", "momentum entry")):
            executed.append(sym)
            trades_today += 1

    mover = biggest_mover(snap)
    posted = None
    if state.get("last_post_date") == today:
        log("DAILY", "publish_skipped last_post_date==today (%s)" % today)
    elif mover:
        kind = "strategy" if int(state.get("post_count") or 0) % 2 == 0 else "discussion"
        path = "/signals/strategy" if kind == "strategy" else "/discussion"
        resp = api(c, "POST", path, {"market": "us-stock", "symbols": [mover["sym"]],
                                     "content": post_content(mover, snap)})
        if "_error" in resp:
            log("DAILY", "publish_error %s post (%s)" % (kind, resp["_error"]))
        else:
            posted = kind
            state["post_count"] = int(state.get("post_count") or 0) + 1
            state["last_post_date"] = today
            log("DAILY", "published %s post signal_id=%s market=us-stock symbols=%s"
                % (kind, resp.get("id") or resp.get("signal_id"), mover["sym"]))
    else:
        log("DAILY", "publish_skipped no movers in snapshot")

    state[tkey] = trades_today
    state["last_daily_run"] = today
    for k in [k for k in state if k.startswith("trades_") and k != tkey][-7:-1]:
        del state[k]
    tmp = os.path.join(DATA_DIR, "state.json.tmp")
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, os.path.join(DATA_DIR, "state.json"))

    print(json.dumps({"ok": True, "date": today, "trades": executed,
                      "trades_today": trades_today, "post": posted,
                      "vetoes": sorted(vetoes)}, sort_keys=True))


if __name__ == "__main__":
    main()
