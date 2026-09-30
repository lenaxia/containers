#!/usr/bin/env python3
"""DD gate: TradingAgents deep-dive on trade.py buy candidates. VETO-ONLY authority.

Runs inside the TradingAgents venv (invoked as:
  integration/vendor/TradingAgents/.venv/bin/python dd_screen.py)

Flow: (1) run trade.py for today's candidates; (2) TA debate per symbol
(MAX_DEBATE_ROUNDS=1, temperature 0); (3) map PM verdict:
  Buy/Overweight -> pass | Hold -> pass_with_caution
  Underweight/Sell -> veto | REVIEW/error/timeout -> abstain (never blocks)
Output: /workspace/ai4trade/dd_verdicts_<date>.json + dd_verdicts.json (latest)
+ one log line per symbol. The LLM can only REMOVE candidates, never add.
"""
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

WS = "/workspace/ai4trade"
TA_DIR = WS + "/integration/vendor/TradingAgents"
MAX_CANDIDATES = 3
SYMBOL_TIMEOUT_S = 20 * 60

MAPPING = {"buy": "pass", "overweight": "pass", "hold": "pass_with_caution",
           "underweight": "veto", "sell": "veto", "review": "abstain"}


def log(line):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(WS + "/log.txt", "a") as f:
        f.write("%s DDGATE %s\n" % (now, line))


def load_ta_env():
    env = dict(os.environ)
    try:
        with open(TA_DIR + "/.env") as f:
            for l in f:
                l = l.strip()
                if l and not l.startswith("#") and "=" in l:
                    k, _, v = l.partition("=")
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass
    return env


def run_trade_py():
    out = subprocess.run([sys.executable, WS + "/trade.py"], capture_output=True,
                         text=True, timeout=300, cwd=WS)
    try:
        return json.loads(out.stdout)
    except Exception:
        return {"entries": [], "_error": out.stdout[:200] + out.stderr[:200]}


def ta_debate(sym, portfolio, result):
    try:
        os.chdir(TA_DIR)
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        cfg = dict(DEFAULT_CONFIG)
        cfg["max_debate_rounds"] = 1
        cfg["max_risk_rounds"] = 1
        cfg["quick_think_llm_provider"] = "openai"
        cfg["deep_think_llm_provider"] = "openai"
        ta = TradingAgentsGraph(config=cfg)
        trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state, signal = ta.propagate(sym, trade_date, portfolio=portfolio)
        rating = (signal or "").strip().lower()
        verdict = MAPPING.get(rating, "abstain")
        thesis = ""
        try:
            thesis = (state.get("trader", {}).get("plan") or "")[:400]
        except Exception:
            pass
        result.update({"symbol": sym, "verdict": verdict, "rating": signal,
                       "thesis_excerpt": thesis, "error": None})
    except Exception as e:
        result.update({"symbol": sym, "verdict": "abstain", "rating": None,
                       "thesis_excerpt": "", "error": str(e)[:200]})


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    decision = run_trade_py()
    cands = [e["symbol"] for e in decision.get("entries", [])][:MAX_CANDIDATES]

    state = {}
    try:
        state = json.load(open(WS + "/state.json"))
    except Exception:
        pass
    holdings = state.get("sleeve_holdings") or {}
    portfolio = {"cash": decision.get("account", {}).get("cash", 100000),
                 "holdings": {k: {"quantity": v} for k, v in holdings.items()}}

    out = {"date": today, "generated_utc": now.isoformat(), "candidates": cands,
           "verdicts": [], "note": "veto-only: LLM may remove candidates, never add"}
    for sym in cands:
        res = {"symbol": sym}
        t = threading.Thread(target=ta_debate, args=(sym, portfolio, res), daemon=True)
        t.start(); t.join(SYMBOL_TIMEOUT_S)
        if t.is_alive():
            res["verdict"] = "abstain"; res["error"] = "timeout after %ds" % SYMBOL_TIMEOUT_S
        out["verdicts"].append(res)
        log("%s %s (rating=%s) %s" % (sym, res.get("verdict"), res.get("rating"),
                                      (res.get("error") or "")[:120]))

    path_d = WS + "/dd_verdicts_%s.json" % today
    with open(path_d, "w") as f:
        json.dump(out, f, indent=2)
    with open(WS + "/dd_verdicts.json", "w") as f:
        json.dump(out, f, indent=2)
    if not cands:
        log("no candidates today — nothing to debate")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
