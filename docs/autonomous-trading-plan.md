# Autonomous Trading System — Design Plan

Status: **proposal / plan** (no core implementation yet — draft code only).
Scope: evolve the current manual DCA + take-profit workflow into an autonomous, backtested,
monitored trading system on Kraken, reusing the existing Supabase schema and pipeline where sound.

---

## 1. Measured baseline (from the live database, 2026-07-09)

Snapshot of actual usage (read-only queries against `ledgers`, `trades`, `trades_history`, `realized_pnl`;
spot prices BTC $62,612 / ETH $1,749):

| Metric | Value |
|---|---|
| Cash deposited | $5,000 (12 deposits) |
| **Deposit fees** | **$190.52 (3.8%)** — card/instant funding |
| Capital deployed into buys | $4,964 across 84 buy legs |
| Buy batch sizes observed | mostly $50 ($49.26 + $0.74 fee); also $25, $100, $200 variants |
| **Buy fee rate** | **1.50%** (Kraken *Instant Buy* — `spend`/`receive` ledger types, not spot orders) |
| Sell fee rate | 0.40% (spot market taker, via the web app's `AddOrder`) |
| Realized round trips | 6 (5 BTC, 1 ETH), avg gain +4.15%, range +0.86% to +8.0% |
| Realized net gain | **+$8.98** |
| Avg holding period (winners) | 121 days |
| Open lots | 78 (59 BTC + 19 ETH), cost + fees $4,804 |
| **Unrealized P&L** | **−$1,632 (−34%)** — every one of the 78 open lots is underwater |
| Total fees paid (deposit + buy + sell) | **≈ $266 — 30× the realized gains** |

Two conclusions fall out immediately:

1. **The cost structure dominates returns.** A $50 lot pays 1.5% on entry and 0.4% on exit:
   ~1.9% round trip before the market moves. A "+2% take profit" is roughly break-even; the
   observed +0.86% exit was a net loss once entry fee is included in the basis. Fixing fees
   (spot limit orders + cheaper funding) is worth more than any strategy change.
2. **Take-profit-only DCA has no exit for downtrends.** Cash converts into inventory that can
   only leave at a profit, so in a falling market capital gets locked (78/78 lots stuck, some
   bought at BTC $110k vs $62.6k today). The strategy realized $9 while accumulating $1,632
   of open losses. Any candidate strategy must bound inventory, not just pick entries.

---

## 2. Flaws in the current app (to fix before autonomy)

### Strategy-level
- **F1 — Instant Buy path (1.5% fee)**: buys are made outside the app (Kraken app recurring/instant
  buy). The bot must place **spot limit post-only orders** via the API instead: maker fee 0.25%
  (less at volume) → ~6× cheaper entries.
- **F2 — Funding cost**: $190 of deposit fees on $5k. Use ACH/wire funding (free/cheap) — an
  operational rule, but it belongs in the system's cost model.
- **F3 — No downside policy**: no stop-loss, no time-based exit, no max-inventory cap, no trend
  filter. Budget also isn't enforced ("$500 in $50 batches" was the intent; $4,964 is deployed).
- **F4 — Take-profit threshold ignores fees**: exits as low as +0.86% gross. Minimum viable TP
  must be `entry_fee% + exit_fee% + slippage + margin`.

### Engineering-level
- **F5 — Double-sell race** (`web/app/actions/trades.ts`): `markTradeAsSold` never checks the lot
  is still `available` before placing a **live market order**. A double click or two sessions fire
  two real sells of the same volume. Fix: optimistic lock (`UPDATE … SET status='selling' WHERE
  status='available'` and check affected rows) *before* calling Kraken.
- **F6 — Non-atomic order + DB write**: the order is placed, then the DB update may fail (the code
  even throws "Kraken order placed but DB update failed"). There is no persisted record of intent
  before the order goes out, and no reconciliation loop. Fix: an `orders` table with a state
  machine (`pending → submitted → filled → reconciled/failed`) written *before* the API call, plus
  reconciliation from Kraken `OwnTrades`/`ClosedOrders` as the source of truth.
- **F7 — No idempotency**: `AddOrder` is called without `userref`/client order id. A timeout +
  retry double-orders. Kraken supports `userref` — use the `orders.id` for it.
- **F8 — `realized_pnl` breaks on partial fills**: the join `trades.order_txid = trades_history.order_txid`
  assumes one fill per order. A market order that fills in 2+ trades produces 2+ rows for one
  buy lot → PK violation aborts the whole insert, and `proceeds_usd`/`fees` would be per-fill,
  not per-order. Fix: aggregate `trades_history` by `order_txid` (SUM cost/fee, MIN time) before joining.
- **F9 — Full re-pagination every sync**: `ledgers.py`/`trades_history.py` re-fetch the entire
  account history (50 rows/req, 1s sleep) on every run. O(history) growth. Use Kraken's `start`
  parameter from the newest stored `time` (minus a small overlap window).
- **F10 — Nonce = millisecond timestamp** in both clients: two requests in the same ms collide;
  concurrent bot + web usage will hit `EAPI:Invalid nonce`. Use a monotonic counter, and separate
  API keys per component (bot / web / pipeline) so nonces never interleave.
- **F11 — Money in `double precision`**: `trades`, `realized_pnl` use floats. Use `numeric`.
  Also `String(trade.volume)` can serialize float artifacts (e.g. `7.5e-05`) into an order.
- **F12 — Sell legs are orphans**: sells insert into `trades` as `side='sell', status='executed'`
  rows with no link to the buy lot they closed (linkage exists only as `order_txid` stamped on the
  buy row). Lot accounting should be explicit (see `orders` + `lots` below).
- **F13 — Ticker is the only price feed**, cached 30s, client-side P&L uses live bid vs
  server-side realized numbers — two different truths. The bot needs its own price/candle store
  (also needed for backtesting).

---

## 3. Target architecture

Everything new is Python at the repo root (matching the pipeline); the web app stays the
read/monitor/manual-override surface.

```
                 ┌────────────────────────────────────────────────┐
                 │  bot/ (new, Python)                            │
 Kraken OHLC ───▶│  data.py       candles → market_data table     │
                 │  strategies/   Strategy interface + 3 impls    │
                 │  risk.py       budget, caps, kill switch       │
                 │  executor.py   intents → orders state machine  │──▶ Kraken AddOrder
                 │  reconcile.py  OwnTrades → fills → lots        │◀── Kraken OwnTrades
                 │  monitor.py    snapshots, guardrails, alerts   │
                 └───────────────┬────────────────────────────────┘
                                 │ Supabase (shared)
   existing: ledgers, trades_history, trades, realized_pnl
   new:      orders, lots, market_data, strategy_config, equity_snapshots, bot_events
                                 │
                 ┌───────────────▼────────────────┐
                 │ web/ dashboard                 │
                 │  + /performance page           │
                 │  + kill-switch / mode toggle   │
                 └────────────────────────────────┘
```

**Modes** (a `strategy_config.mode` column, honored by the executor):
- `off` — nothing runs.
- `paper` — full loop runs; orders are checked with Kraken `AddOrder validate=true` (syntax/funds
  validation, **never executes**), fills are simulated against live ticker and recorded with
  `mode='paper'`. This is the forward-testing substitute that costs nothing.
- `live` — real orders, gated by the risk manager.

**Scheduling — decided: GitHub Actions cron.** A single stateless entry point `python -m bot.run`:
load config + state from DB, decide, act, exit. No long-lived process to babysit (matches the
existing batch-pipeline style). Draft workflow:

```yaml
# .github/workflows/bot.yml
name: trading-bot
on:
  schedule:
    - cron: "*/15 * * * *"   # best-effort; GH may delay/skip — the bot must tolerate gaps
  workflow_dispatch: {}       # manual trigger for testing
concurrency:
  group: trading-bot          # never two runs at once (protects nonces + order state)
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m bot.run
        env:
          PUBLIC_KEY: ${{ secrets.KRAKEN_BOT_PUBLIC_KEY }}    # bot-dedicated API key (nonce isolation, F10)
          PRIVATE_KEY: ${{ secrets.KRAKEN_BOT_PRIVATE_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          SMTP_APP_PASSWORD: ${{ secrets.SMTP_APP_PASSWORD }}
```

Consequences the design must absorb: GH cron is best-effort (runs can be late or skipped —
guardrail "data freshness" tolerates up to 2 missed cycles before alerting, and strategies are
written against *state*, not against an assumed fixed cadence); secrets live in GitHub (use a
**bot-dedicated Kraken API key** with only *Query/Create/Cancel orders* permissions — **no
withdrawal rights** — so a repo compromise can't drain the account); the `concurrency` group
serializes runs so order state and nonces never interleave.

### New tables (draft DDL)

```sql
CREATE TABLE orders (              -- every intent, before it touches Kraken
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('paper', 'live')),
    strategy text NOT NULL,        -- 'dca_tp' | 'dca_dip' | 'grid'
    pair text NOT NULL, side text NOT NULL, ordertype text NOT NULL,
    price numeric, volume numeric NOT NULL,
    userref int NOT NULL,          -- idempotency key sent to Kraken
    state text NOT NULL DEFAULT 'pending',  -- pending|submitted|open|filled|canceled|failed
    kraken_txid text, lot_id bigint,        -- set on submit / for sells
    created_at timestamptz DEFAULT now(), updated_at timestamptz
);

CREATE TABLE lots (                -- explicit inventory (replaces status flags on trades)
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL, strategy text NOT NULL, asset text NOT NULL,
    volume numeric NOT NULL, cost_usd numeric NOT NULL, fee_usd numeric NOT NULL,
    buy_order_id bigint REFERENCES orders (id),
    target_price numeric,          -- pre-computed TP for the lot
    state text NOT NULL DEFAULT 'open',     -- open|exiting|closed
    opened_at timestamptz, closed_at timestamptz
);

CREATE TABLE market_data (         -- candles for signals + backtests
    pair text, "interval" int, ts timestamptz,
    open numeric, high numeric, low numeric, close numeric, volume numeric,
    PRIMARY KEY (pair, "interval", ts)
);

CREATE TABLE strategy_config (     -- editable from the web UI
    key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz
);  -- rows: mode, kill_switch, per-strategy params, budget caps

CREATE TABLE equity_snapshots (    -- monitoring time series (per mode)
    ts timestamptz, mode text, cash_usd numeric, inventory_value_usd numeric,
    unrealized_usd numeric, realized_cum_usd numeric, fees_cum_usd numeric,
    open_lots int, PRIMARY KEY (ts, mode)
);

CREATE TABLE bot_events (          -- structured log + alert trail
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts timestamptz DEFAULT now(), severity text, kind text, detail jsonb
);
```

The existing `ledgers`/`trades_history` sync stays as the independent **reconciliation source**:
what Kraken says happened, matched nightly against what `orders`/`lots` believe happened. Drift
raises an alert (F6/F8 become detectable instead of silent).

---

## 4. Strategies

All three share the lot discipline the app already has (each entry is a lot with its own exit),
the same risk envelope, and fee-aware exits. Common parameters:

| Param | Default | Note |
|---|---|---|
| `budget_usd` | 500 | **decided**: fresh $500, fully separate from the ~$4.8k legacy inventory; hard cap, enforced |
| `batch_usd` | 50 | per-lot size |
| `fee_entry` / `fee_exit` | 0.25% / 0.25% | post-only limit orders both ways |
| `min_tp_pct` | ≥ fees + 0.5% margin | floor for any take-profit |
| `max_open_lots` | budget/batch | inventory cap |

### S1 — Baseline, formalized: fixed-interval DCA + take-profit
What the usage data shows, made explicit and automated:
- Buy `batch_usd` every `interval` (e.g., 3 days — observed cadence is bursty/manual; the
  backtest will sweep 1d/3d/7d), while `deployed < budget_usd`.
- Each lot gets `target_price = entry × (1 + tp_pct)`; place the sell as a **resting limit order
  immediately** after the buy fills (maker fee, and no need for the bot to be online to catch the spike).
- Sweep `tp_pct` ∈ {2%, 4%, 6%, 10%}. Observed avg was 4.15% gross.
- **Known weakness (measured)**: no downtrend exit — this is the control against which the other
  two must justify themselves.

### S2 — Dip-scaled DCA with trend filter + inventory recycling
Same skeleton as S1, two changes aimed directly at the −34% inventory problem:
- **Scale entries by discount**: multiplier on `batch_usd` from the discount to the 30-day SMA —
  e.g. ×0 above +5% (don't buy strength), ×1 at 0–5% below, ×2 at 5–15% below, ×3 beyond. Budget
  cap still binds. (Buys more of the dip the baseline bought anyway, but stops buying rallies.)
- **Inventory recycling instead of hold-forever**: a lot older than `max_age` (e.g. 45 days) has
  its target lowered to `breakeven + fees`; optionally a portfolio-level stop (exit all if equity
  drawdown > `max_dd`, e.g. 25%) — sweep both in backtest, including "no stop" since stops on
  BTC mean-reversion often hurt.
- Hypothesis to test: better cost basis in downtrends, less dead capital, at the price of missing
  some upside when the filter says "don't buy".

### S3 — Grid trading (generalizes the current lot model)
The app's "buy a lot, sell it at +x%" is one rung of a grid; make the whole ladder explicit:
- Define a band `[P_low, P_high]` (e.g. ±25% around current price), `n` rungs spaced `g%` apart
  (g ≥ 2× fees + margin, e.g. 3–5%). Rest a `batch_usd` limit buy at each rung below price; when
  a rung fills, immediately rest its paired sell one rung up.
- Entirely resting limit orders: maker fees, no timing decisions, profits from oscillation —
  fits BTC/ETH chop.
- **Known weakness**: trending markets walk out of the band (below → fully invested inventory,
  exactly like the baseline's failure; above → all cash, missing the run). Mitigations to
  backtest: band recentering after `k` consecutive rung breaches, and reserving part of the
  budget outside the grid.
- Extra operational complexity: many open orders to track (the `orders` state machine is built
  for this).

**Decision rule**: run all three through the backtest protocol (§5) on identical data, fees, and
budget. Rank on risk-adjusted net return (after fees) with max-drawdown and capital-utilization
as tiebreakers — not raw return, since S1 can "win" a pure bull segment while being the strategy
that produced today's −34%.

### Legacy inventory policy (the 78 pre-bot lots) — **decided**

Exit each legacy lot at **≥ +1% net gain** (proceeds after exit fee ≥ 1.01 × (cost + entry fee);
entry fees are sunk, exit assumed maker 0.25%). Mechanically:

- Each lot's target: `target_price = (cost_usd + fee_usd) × 1.01 / (volume × (1 − 0.0025))`.
- Implemented as **resting GTC limit sells** — they execute on recovery without the bot being
  online, at maker fees. Proceeds return to the cash reserve, **not** the bot's budget.
- Reality check at today's prices (BTC $62.6k / ETH $1,749): targets range $64.7k–$113k (BTC)
  and $2,014–$3,288 (ETH). Only 1 of 59 BTC lots triggers within a +5% move; most need +30–60%,
  and no ETH lot triggers before +30%. This policy **parks** legacy capital until recovery —
  it does not free it soon. That's accepted; the alternative (selling at a loss) is explicitly out.
- **Open-order cap**: Kraken limits concurrent open orders by verification tier (can be as low
  as ~60–80). 78 resting sells + the bot's own orders may not fit. The reconcile loop therefore
  maintains a **rolling window**: keep resting sells only for the `n` lots nearest their targets
  (e.g. within 15%), tracked in `lots.state = 'exiting'`; re-evaluate every cycle. Legacy lots
  live in the same `lots` table with `strategy = 'legacy'`.

---

## 5. Backtesting design

No sandbox exists, so the backtester is the primary safety net. Priorities: realistic costs,
identical accounting to production, and honest out-of-sample discipline.

- **Data**: Kraken public OHLC API returns only the last 720 candles per interval — enough for
  recent 1h/4h data, not for years. Sources, in order:
  1. Kraken's downloadable historical OHLCVT CSVs (full history, quarterly updates) → load once
     into `market_data` / local parquet.
  2. `GET /0/public/OHLC` incrementally for the live tail (same loader the bot uses in production).
  Target: ≥ 4 years of 1h candles for XBTUSD + ETHUSD (covers the 2022 bear, 2023–24 recovery,
  2025–26 drawdown — the regime that broke the baseline).
- **Engine** (`backtest/engine.py`): event-driven candle loop. The portfolio is the same lot
  model as production (same dataclasses the executor uses — one accounting implementation,
  two drivers). Fill rules, conservative by construction:
  - limit buy fills if `candle.low ≤ limit` (fill at limit, not at low); limit sell if `high ≥ limit`;
  - market orders fill at `open` of the *next* candle ± slippage (half spread + 5 bps);
  - fee model per order type: maker 0.25% / taker 0.40% / instant 1.5% — so we can also replay
    the baseline *as it was actually traded* to validate the engine against the real `realized_pnl` rows.
- **Metrics** (per strategy × param set × asset): net P&L after fees, CAGR, max equity drawdown,
  Sharpe/Sortino, fee drag ($ and % of gross), win rate, median holding days, capital
  utilization (avg deployed / budget), % time fully invested, and the same vs **buy-and-hold**
  and **hold-cash** benchmarks.
- **Protocol against overfitting**: walk-forward — optimize params on a rolling 12-month window,
  test on the following 3 months, roll forward; report only the stitched out-of-sample equity
  curve. Prefer parameter *plateaus* over sharp peaks. Also report per-regime slices (bull /
  bear / chop) so we know *when* each strategy loses.
- **Validation of the engine itself**: replay the actual baseline trades (dates/sizes from
  `ledgers`) through the engine with the instant-buy fee model; engine-computed realized P&L
  must match the 6 rows in `realized_pnl` within rounding. This gates everything else.

Draft strategy interface (shared by backtest and live executor):

```python
@dataclass
class Candle: ts: datetime; open: float; high: float; low: float; close: float; volume: float

@dataclass
class Intent:   # what a strategy wants; risk manager may veto/shrink
    side: Literal["buy", "sell"]; pair: str; ordertype: Literal["limit", "market"]
    volume: float; price: float | None; lot_id: int | None; reason: str

class Strategy(Protocol):
    name: str
    def on_candle(self, candle: Candle, portfolio: Portfolio, params: dict) -> list[Intent]: ...
```

---

## 6. Execution engine (autonomous loop)

Per run (`python -m bot.run`, every 15 min via scheduler):

1. **Sync**: pull latest candles → `market_data`; reconcile open `orders` against Kraken
   (`ClosedOrders`/`OwnTrades`) → update `orders.state`, create/close `lots`. *Paper mode:
   simulate fills against the current ticker instead.*
2. **Guardrails** (risk.py, hard-fails the run with a `bot_events` alert):
   kill switch off? config sane? data fresh (< 2 intervals old)? deployed ≤ budget?
   open lots ≤ cap? daily order count ≤ limit? drift between `lots` and nightly
   ledger reconciliation = 0?
3. **Decide**: active strategy's `on_candle(...)` → intents.
4. **Execute**: for each intent surviving risk checks — insert `orders` row (`pending`) →
   call `AddOrder` with `userref=orders.id` (+ `validate=true` in paper mode) → update to
   `submitted`/`failed`. Volume/price formatted to Kraken's pair decimals from `AssetPairs`,
   never `str(float)`.
5. **Snapshot**: write `equity_snapshots` row; emit events.

Crash-safety: every state transition is persisted before the external call it precedes, so a
crash at any point is recoverable by the next run's reconcile step (fixes F6). A `userref`
already submitted is never resubmitted (fixes F7).

The web app gains: `/performance` page, a mode/kill-switch control, and the existing manual
sell button is rewired through the same `orders` path (fixing F5 via the optimistic lock).

---

## 7. Monitoring tool

`bot/monitor.py` — runs at the end of every bot cycle plus a nightly deep pass:

- **Time series** (`equity_snapshots`): equity, cash, inventory value, unrealized/realized,
  cumulative fees — per mode, so the paper strategy's live forward-test is directly comparable
  to backtest expectations ("is live tracking the backtest?" is *the* monitoring question).
- **Guardrail alerts** (`bot_events` + push): drawdown breach, order failure/rejection, stale
  market data, sync drift (ledger reconciliation mismatch), budget/inventory cap hits, kill
  switch activations. **Delivery — decided: email.** SMTP via Gmail app password
  (`SMTP_APP_PASSWORD` secret) from the GitHub Actions run; severity `error`+ emails immediately,
  `warn` batches into the weekly report. Two free backstops: GitHub emails on workflow *failure*
  automatically (catches crashes before our own alerting runs), and every alert is also a
  `bot_events` row so the dashboard shows history even if mail delivery fails.
- **Dashboard** (`web/app/performance/`): equity curve vs buy-and-hold benchmark; open-lot aging
  histogram (age × distance-to-target — would have made today's 78-lots-underwater visible
  months ago); realized vs unrealized split; fee drag; per-strategy KPI cards; recent
  `bot_events` feed.
- **Weekly report**: one scheduled job posts a summary (return, drawdown, fees, lots opened/
  closed, alerts) so performance review doesn't rely on remembering to look.

---

## 8. Roadmap

| Phase | Deliverable | Acceptance criteria |
|---|---|---|
| **0. Foundations** | Fee fix decision (API limit orders + ACH funding); fix F5 double-sell lock, F8 partial-fill aggregation, F9 incremental sync, F10 nonce; new tables migrated | manual sell path is race-safe; pipeline run is O(new rows); `realized_pnl` correct on a synthetic partial fill |
| **1. Data + backtester** | OHLC loader (historical CSVs + API tail); engine + metrics + walk-forward harness | engine replays the real baseline trades and matches `realized_pnl` within rounding |
| **2. Strategy study** | S1/S2/S3 implemented against the Strategy interface; walk-forward report | written comparison with out-of-sample equity curves per regime; parameters chosen from plateaus; go/no-go per strategy |
| **3. Paper bot** | executor + risk manager + reconcile loop in `paper` mode on a 15-min schedule | ≥ 2 weeks unattended paper run: zero unreconciled orders, zero guardrail false-negatives, paper equity tracks backtest expectation |
| **4. Monitoring** | snapshots, alerts (email), `/performance` page, weekly report | drawdown/staleness/drift alerts land in the inbox in induced-failure tests |
| **5. Gated live** | live mode with `budget_usd=100`, kill switch, then scale to $500 | 4 weeks live within guardrails and tracking paper before budget increases |
| **6. Legacy exit rollout** | import the 78 lots as `strategy='legacy'`; rolling-window resting limit sells at +1% net | every legacy lot has a stored target; nearest-target lots have live GTC sells; window respects the open-order cap |

Phase 0 and 1 are independent and can run in parallel. Nothing trades live before Phase 5, and
paper mode never places an executable order (`validate=true` only). Phase 6 places live *limit
sell* orders only (no buys, no market orders) and can ship as soon as the orders state machine
(Phase 0) is trusted — it doesn't need to wait for the strategy study.

---

## 9. Decisions (2026-07-09)

1. **Legacy 78 lots**: exit at **≥ +1% net gain** via resting limit sells (rolling window under
   the open-order cap). No selling at a loss. Proceeds go to cash reserve, not the bot budget.
2. **Bot budget**: fresh **$500**, hard-capped, fully separate from legacy inventory.
3. **Alerts**: **email** (Gmail SMTP app password; GH Actions failure emails as backstop).
4. **Scheduler**: **GitHub Actions cron** (15-min best-effort, `concurrency` serialized,
   bot-dedicated no-withdrawal Kraken API key in repo secrets).

Still open (non-blocking): whether monitoring should report staking yield (BABY / ETH staking
ledger rows) as a passive-income line item.
