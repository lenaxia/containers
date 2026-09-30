#!/usr/bin/env python3
"""Live US-stock snapshot for the ai4trade automations (stocks only, by design).

Usage: marketdata.py [EXTRA_TICKER ...]

Prints one JSON object: {fetched_at_utc, stocks: [...]} with price, 1d and 5d
change, 52-week range when available. Source: Yahoo Finance chart API.
Each ticker degrades to an error object independently.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
DEFAULTS = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META", "GOOGL", "AMD"]
UNIVERSE_FILE = "/workspace/ai4trade/universe.txt"


def _universe():
    try:
        out = []
        with open(UNIVERSE_FILE) as f:
            for l in f:
                l = l.strip()
                if not l or l.startswith("#"):
                    continue
                out.extend(l.split())
        return [t.upper() for t in out]
    except Exception:
        return []


def get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def yahoo(sym):
    d = get("https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d" % sym)
    res = d["chart"]["result"][0]
    meta = res["meta"]
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    chg_1d = round((price / prev - 1) * 100, 2) if (price and prev) else None
    closes = []
    try:
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    except Exception:
        pass
    chg_5d = round((price / closes[0] - 1) * 100, 2) if (price and len(closes) >= 2) else None
    return {
        "sym": sym,
        "price": price,
        "prev_close": prev,
        "chg_1d_pct": chg_1d,
        "chg_5d_pct": chg_5d,
        "week_52_high": meta.get("fiftyTwoWeekHigh"),
        "week_52_low": meta.get("fiftyTwoWeekLow"),
        "regular_market_time": meta.get("regularMarketTime"),
    }


def main():
    extra = [a.upper() for a in sys.argv[1:] if a.isalpha() or "-" in a]
    syms = list(dict.fromkeys(DEFAULTS + _universe() + extra))
    stocks = []
    for s in syms:
        try:
            stocks.append(yahoo(s))
        except Exception as e:
            stocks.append({"sym": s, "error": str(e)[:120]})
    print(json.dumps({
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "stocks": stocks,
    }))


if __name__ == "__main__":
    main()
