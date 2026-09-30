# FORWARD TRACKER — conventions, rules, limitations

Out-of-sample (OOS) forward evidence machine for the strategy lab. Both
backtest labs concluded **nothing passes multiple-testing correction** on 3y
of history (v1: 137 variants, best DSR 0.91 < 0.95; v2: 307 trials, best DSR
0.86 < 0.95), so promotion decisions require forward evidence
(research/notes.md TOP-10 #2: "Treat 3y as a screen, forward-test as the
evidence"). This directory collects that evidence, one session at a time.

**Local simulation only.** Virtual money (100,000 per variant), no brokerage
or trading-platform API is ever called. The only network use is Yahoo's
public daily-OHLC endpoint for data refresh.

## Daily operation

```
python3 /workspace/ai4trade/forward/forward.py
```

Stdlib only (no venv needed). Each run: refetch data -> replay everything ->
atomically overwrite `forward_state.json` -> print one comparison JSON to
stdout. Run once per UTC day, ideally after the US close (>= ~21:00 UTC);
running earlier can record that session's *partial* bar, which will be
revised on a later fetch only while it sits in the trailing 5-bar revision
window (see data conventions). Cron example (21:30 UTC Mon-Fri):

```
30 21 * * 1-5  python3 /workspace/ai4trade/forward/forward.py >> /workspace/ai4trade/forward/run.log 2>&1
```

## Core conventions

- **No lookahead**: every signal is computed from closes through `t-1`;
  execution is at the close of day `t`. Positions established at close `t`
  earn day `t+1`'s close-to-close return.
- **Forward window**: starts 2026-09-29. All history before that is warm-up
  only (state carry: holdings, entry prices, cadence phase) — its equity path
  is discarded. Each variant starts from 100,000 virtual at the window start.
- **Costs**: 5 bps per side on one-way turnover. No other friction.
- **Long-only, no leverage**, gross exposure <= 1, remainder = cash.
- **Deterministic**: state is a pure function of the CSVs in `forward/data/`;
  a double-replay guard inside every run asserts identical output.
- **Idempotent per UTC day**: the whole state is recomputed and rewritten
  atomically (`tmp` + rename) each run; equity series are keyed by session
  date, so re-running the same day overwrites — it never double-appends.
- **Universe**: 12 tradeable names (NVDA AAPL MSFT TSLA AMZN META GOOGL AMD
  JPM XOM LLY AVGO); SPY = benchmark; QQQ loaded but not tracked (v1 lab
  convention: both ETFs held out of the tradeable universe).

### Engine accounting (two documented paths)

- **Variants 1-4 (v1 lab)**: exact copy of `lab/backtest.py run_variant`
  semantics. Portfolio weights drift with prices between targets; on a
  target day, turnover = |target - drifted| summed over names; daily
  multiplier = `(1 + r_day) * (1 - cost)` with cost charged on the trade
  day. Cross-validated bit-exact against the lab engine (max daily
  multiplier diff 0.0; validation totals identical to lab/results.json).
- **Variants 5-6 (v2 lab2)**: exact port of `lab2/families.py` weight rows +
  `lab2/engine.py` killswitch accounting. Effective weights are the (possibly
  overlaid) target rows `W2[t]`; daily multiplier = `1 + r - cost` with
  `r = W2[t-1]·ret[t]`, cost = 5bps x |target_t - W2[t-1]| charged same day.
  Cross-validated against lab2's pandas code (W rows 0/751 mismatched;
  forward multipliers bit-exact). Note lab2's *metrics* engine
  (`engine.backtest`) charges cost one day later; the cumulative difference
  is ~4e-5 over a 313-day window, and the killswitch's own accounting —
  which is what variants 5-6 follow — charges same-day.
- **V306 trigger-day quirk (inherited from lab2 verbatim)**: the cost of
  trading *to* the base target is charged on the day the drawdown triggers,
  even though the overlay then flattens to cash; the flatten itself is
  uncharged. Logged trades reflect actual effective-weight changes.

### Data conventions

- `forward/data/` is owned by the tracker, seeded once from the read-only
  `lab/data/` CSVs, then refetched every run (same Yahoo v8 chart endpoint,
  UA header and 2-attempt retry as `lab/data/fetch.py`; range=3y, interval=1d).
- **Append-mostly merge**: new dates append; only the trailing
  `REVISION_TAIL = 5` existing bars may be revised by a fetch (handles late
  corrections and same-session partial bars); deeper history is frozen so the
  warm-up replay is stable run-to-run. If a symbol's fetch fails, its
  existing file is kept and the manifest marks it `stale`.
- Symbols align on the intersection calendar (currently identical; any
  misaligned rows are dropped and counted in `meta.data.dropped_misaligned_rows`).
- Prices are raw (unadjusted) closes, as in both labs.

## The 6 tracked variants (exact rules)

1. **don_p10_s8** — v1 Donchian sleeve breakout. Each of the 12 names has a
   fixed 1/12 sleeve. Enter a sleeve when its close is within 10% of its
   trailing 63-session closing high (max of the last 63 closes through
   t-1); exit when a close falls 8% below the entry *fill* price; re-entries
   allowed. Weights drift between signals.
2. **mom_n5_k5_abs_c21** — v1 cross-sectional momentum. Rank the 12 names by
   5-session return through t-1; hold the top 5 equal-weight (1/5 each);
   names with return <= 0 are excluded (slots go to cash). Rebalance every
   21 *trading* sessions (cadence anchored at warmup index — note: the
   orchestrator brief said "weekly cadence", but the variant id `c21` and
   `lab/forward_variants.json` params both say 21d; implemented as 21d).
3. **mom_n21_k5_abs_c1** — same family, 21-session lookback, top-5, absolute
   filter, daily (every 1 session) rebalance.
4. **base_ew12** — buy-and-hold control: fixed 1/12 weight in each of the 12
   names, bought once at the first execution close of the warm-up, then
   weights drift forever (v1 `Fixed`).
5. **V228_meanrev_vol_n1_k2_y10_sel3** — lab2 vol-scaled mean reversion
   (`meanrev_vol`, results.json id V228, params n=1, kvol=2.0, y=10.0,
   sel=3). Candidates: names whose 1-session return through t-1 is
   <= -2.0 x sigma20 (per-name sample stdev of the last 20 daily returns
   through t-1; sigma20 * sqrt(1)). Buy the *worst* qualifying names
   worst-first, up to 3 concurrent, each at 1/3 weight (unfilled slots =
   cash); entry fill price = execution-day close. Exit when a close is
   >= +10% (take-profit) or <= -5% (stop) vs the entry fill price; same-day
   exit+re-entry of a name is allowed. Base weights stay 1/3 while held
   (no drift, no rebalancing turnover).
6. **V306_killswitch_V228** — V228 overlaid with a portfolio killswitch:
   if the variant's forward-window equity falls to <= -10% from its running
   peak (peak marked on close, net of costs), flatten to cash for 20
   sessions, then resume the base weights and reset the peak reference.
   Overlay equity/peak reset at the forward window start (mirroring lab2's
   per-split reset); the effective weight row carries across the boundary.
   Note the orchestrator brief described V228 as "buy worst 1d performer"
   (singular); lab2's V228 params say sel=3 — the lab2 params are
   authoritative per the "use lab2 conventions exactly" instruction.

## State & output

`forward_state.json` (rewritten whole each run):
- `meta` — engine/convention summary, data fetch manifest, warm-up range.
- `benchmark.SPY.series` — SPY buy-and-hold equity (100,000 base; reference
  = last close strictly before the window so the benchmark earns day 1 like
  the variants; no costs applied).
- `variants.<id>` — `equity_series` [{date, equity, exposure}] for forward
  sessions only; `current_positions` {sym: {qty, weight, last_price, value,
  entry_date}} as of `as_of_date` (positions carried into the window show
  `entry_date: null` — they pre-date it); `trades` [{date, action, symbol,
  qty, reason, price}] (qty = fractional shares at the execution close);
  `return_to_date`, `trade_count`, `current_/avg_exposure`, and for V306
  `killswitch_fires` {warmup, forward}.
- While the window has no session data yet (today at init: Yahoo's last
  completed bar is 2026-09-28), `equity_series` holds a single
  window-start anchor row (100,000) which the first real session close
  replaces.

The stdout comparison JSON prints per variant: return-to-date, current
positions (weights), trade count, current/avg exposure, current equity —
plus the SPY benchmark return and full series, window day count, and the
last data date.

## Known limitations

- **Warm-up reuse of possibly-refetched history**: path-dependent state
  (Donchian entry prices, meanrev held/entry state, cadence phases) carries
  from replayed history. The frozen-history merge keeps this stable, but
  revisions inside the trailing 5-bar window can in principle nudge
  warm-up state, and Yahoo's 3y fetch window slides forward over time
  (dropped old bars remain in our CSVs; nothing is ever re-derived from a
  changed distant past except via that frozen tail).
- **Single-price close marks**: OHLC input is used only for the close; no
  intraday path, so stop/target exits fill at session closes, not at the
  level itself (same as both labs).
- **No slippage beyond 5 bps/side**: no spread, impact, borrow, or
  short-sale mechanics (long-only).
- **Raw unadjusted closes**: no dividend/split handling. A corporate action
  in a tracked name would distort returns until the data provider's history
  revises (only the trailing 5 bars auto-revise; a deep split adjustment
  would need a manual reseed from `lab/data`).
- **Benchmark is cost-free SPY** buy-and-hold (single reference purchase);
  variants pay costs.
- **Killswitch state resets at the window start** (per-split lab2
  semantics): a drawdown spanning the warm-up/forward boundary is measured
  only from the forward peak.
- **Intraday partial-bar risk**: run after the US close; a partial bar
  recorded pre-close is revised on later fetches only within the trailing
  5-bar window.
- **Fractional shares / weight-based sizing**: qty figures are analytic
  (weight x pre-cost equity / price), not executable lot sizes.
- **Small-sample honesty**: with <= 3 months of forward data nothing here is
  statistically meaningful; the point is a clean, untainted, append-mostly
  record for later evaluation (the labs' DSR machinery applies at the end,
  not daily).

## Cross-validation performed (2026-09-29, init)

- v1 engine vs `lab/backtest.py` on the same data: daily multipliers
  bit-identical (max diff 0.0) for all 4 v1 variants; validation-window
  total returns match lab/results.json to the last digit.
- v2 `meanrev_vol` rows vs `lab2/families.py` (venv pandas): 0/751 rows
  mismatched.
- v2 chain vs lab2 accounting: V228 validation total 0.8088642 (mine,
  same-day cost) vs 0.8088261 (lab2 engine, next-day cost) — the documented
  timing difference only.
- V306 overlay vs a lab2 `apply_killswitch` replication with the tracker's
  boundary: fire counts equal (4 warm-up, 0 forward at a synthetic
  boundary), forward multipliers bit-identical, final holdings equal
  (AVGO/JPM/XOM — the state V228 entered the window with).
- End-to-end simulated "day 2 / day 3" (synthetic 2026-09-29/30 bars,
  sandboxed): equity rows recorded, trades generated with correct notionals,
  SPY series computed, same-data rerun byte-identical, next-day append clean.
