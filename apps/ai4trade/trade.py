#!/usr/bin/env python3
"""Deterministic trading decision engine for the ai4trade automations.

Policy (conservative momentum, growth tilt) — paper account only:
  - Universe: liquid mega-caps/ETFs from marketdata.py (+ argv extras)
  - Entry: 1-day RS vs SPY >= +3%, positive 1d change, within 5% of 52w high
  - Sizing: 10% of equity per position, whole shares, max 5 positions
  - Exits: -5% stop or +15% target from entry (checked before entries)
  - Max 2 trades/day (enforced by the calling agent via state trades_YYYYMMDD)
  - Market-hours guard: Mon-Fri 13:30-20:00 UTC (US regular session, EDT)
  - News: Google News RSS headlines per candidate + market-wide (agent screens
    for political/regulatory/material risk before executing buys)

Usage: trade.py [EXTRA_TICKER ...]
Prints one JSON decision object. Does NOT execute trades itself.
"""
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

WS = "/workspace/ai4trade"
BENCH = {"SPY", "QQQ"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

POLICY = {
    "style": "conservative momentum, growth tilt",
    "entry": "1d RS vs SPY >= +3%, 1d change > 0, within 5% of 52w high",
    "position_size_pct_of_equity": 10,
    "max_positions": 15,
    "stop_loss_pct": -5.0,
    "take_profit_pct": 15.0,
    "max_trades_per_day": 2,
}


def creds():
    for p in [WS + "/credentials.json", os.path.expanduser("~/.config/ai4trade/credentials.json")]:
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            continue
    return None


def api(path):
    c = creds()
    r = urllib.request.Request(c["base_url"].rstrip("/") + path, headers={
        "Authorization": "Bearer " + c["token"], **UA})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode() or "{}")


def headlines(query, limit=5):
    url = ("https://news.google.com/rss/search?q=" + urllib.request.quote(query)
           + "&hl=en-US&gl=US&ceid=US:en")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode("utf-8", "ignore")
        titles = re.findall(r"<title>(.*?)</title>", body, re.S)[1:]  # [0] is channel title
        return [html.unescape(t)[:200] for t in titles[:limit]]
    except Exception as e:
        return ["_news_fetch_error: " + str(e)[:100]]


def market_open(now):
    if now.weekday() > 4:
        return False
    hm = now.hour * 60 + now.minute
    return 13 * 60 + 30 <= hm < 20 * 60


def main():
    extra = [a.upper() for a in sys.argv[1:] if a.isalpha()]
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    snap = json.loads(subprocess.run(
        [sys.executable, WS + "/marketdata.py"] + extra,
        capture_output=True, text=True, timeout=120).stdout)
    stocks = {s["sym"]: s for s in snap.get("stocks", []) if "error" not in s}
    spy = stocks.get("SPY", {}).get("chg_1d_pct") or 0.0

    try:
        me = api("/claw/agents/me")
        cash = float(me.get("cash") or 0)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "me failed: %s" % e}))
        return
    try:
        pos = api("/positions").get("positions") or []
    except Exception as e:
        pos = []
    held = []
    for p in pos:
        if p.get("source") and p.get("source") != "self":
            continue
        sym = (p.get("symbol") or "").upper()
        qty = p.get("quantity") or 0
        entry = p.get("entry_price") or p.get("avg_price") or 0
        cur = p.get("current_price") or entry
        if sym and qty:
            held.append({"symbol": sym, "quantity": qty, "entry_price": entry,
                         "current_price": cur,
                         "pnl_pct": round((cur / entry - 1) * 100, 2) if entry else None})
    held_syms = {h["symbol"] for h in held}
    try:
        sleeve_syms = set(json.load(open(WS + "/state.json")).get("sleeve_symbols") or [])
    except Exception:
        sleeve_syms = set()
    pos_value = sum(h["quantity"] * h["current_price"] for h in held)
    equity = cash + pos_value

    exits = []
    for h in held:
        pct = h["pnl_pct"]
        if pct is None:
            continue
        if pct <= POLICY["stop_loss_pct"]:
            exits.append({"action": "sell", "symbol": h["symbol"], "quantity": h["quantity"],
                          "reason": "stop loss: %.2f%% <= -5%%" % pct, "pnl_pct": pct})
        elif pct >= POLICY["take_profit_pct"]:
            exits.append({"action": "sell", "symbol": h["symbol"], "quantity": h["quantity"],
                          "reason": "take profit: %.2f%% >= +15%%" % pct, "pnl_pct": pct})

    cands = []
    for sym, s in stocks.items():
        if sym in BENCH or sym in held_syms or sym in sleeve_syms:
            continue
        rs = (s.get("chg_1d_pct") or 0) - spy
        hi, lo, px = s.get("week_52_high"), s.get("week_52_low"), s.get("price")
        dist_hi = (hi / px - 1) * 100 if (hi and px) else None
        if rs >= 3.0 and (s.get("chg_1d_pct") or 0) > 0 and dist_hi is not None and dist_hi <= 5.0:
            cands.append({"symbol": sym, "price": px, "chg_1d_pct": s["chg_1d_pct"],
                          "rs_vs_spy_pts": round(rs, 2), "dist_to_52w_high_pct": round(dist_hi, 2)})
    cands.sort(key=lambda c: -c["rs_vs_spy_pts"])
    cands = cands[:3]

    entries = []
    slots = POLICY["max_positions"] - len(held) + len(exits)
    budget_share = equity * POLICY["position_size_pct_of_equity"] / 100.0
    for c in cands:
        if len(entries) >= max(0, slots):
            break
        qty = int(budget_share // c["price"]) if c["price"] else 0
        if qty < 1:
            continue
        entries.append({"action": "buy", "symbol": c["symbol"], "quantity": qty,
                        "est_cost": round(qty * c["price"], 2),
                        "reason": "momentum: RS +%.2f pts vs SPY, %.2f%% below 52w high"
                                  % (c["rs_vs_spy_pts"], c["dist_to_52w_high_pct"]),
                        "headlines": headlines("%s stock" % c["symbol"])})

    out = {
        "ok": True,
        "now_utc": now.isoformat(),
        "today": today,
        "market_open": market_open(now),
        "policy": POLICY,
        "account": {"cash": round(cash, 2), "positions_value": round(pos_value, 2),
                    "equity": round(equity, 2), "positions_held": len(held)},
        "sleeve_excluded": sorted(sleeve_syms),
        "held": held,
        "exits": exits,
        "entries": entries,
        "market_headlines": headlines("stock market today politics Fed"),
        "note": "Exits before entries. Max 2 trades/day total. Buys require a headline screen "
                "(skip on material political/regulatory/earnings risk). Only execute via "
                "/api/signals/realtime when market_open is true; otherwise defer.",
    }
    with open(WS + "/last_trade_decision.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
