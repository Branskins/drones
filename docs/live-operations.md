# Live operations runbook

The bot went live on **2026-07-22** (grid on XBTUSD, $500 budget). This is the
operator's reference: current state, the gotchas found during go-live, and the
routine checks. For the original design see `docs/autonomous-trading-plan.md`;
for one-time setup see `docs/human-actions.md`.

## Current live configuration (`strategy_config`)

| key | value | note |
|---|---|---|
| `mode` | `live` | |
| `kill_switch` | `false` | set `true` to halt all cycles immediately |
| `confirm_live` | `true` | gate 2 of 2 (gate 1 is env `ALLOW_LIVE=1` in the workflow) |
| `live_validate_only` | `false` | `true` = AddOrder sent with `validate=true`, executes nothing |
| `active_strategy` | `grid` | |
| `pair` | `XBTUSD` | |
| `budget_usd` | `500` | grid hard cap; legacy inventory is separate |
| `batch_usd` | `50` | per rung |
| `grid` | `{step_pct: 4, band_pct: 25, recenter_pct: 10}` | 7 rungs, −4%…−25% |
| `fee_maker_pct` | `0.40` | **real account rate — not 0.25** (see below) |
| `max_orders_per_day` | `50` | raised from 12 during go-live (see below) |
| `legacy_min_gain_pct` | `1.0` | net-of-fee exit target for legacy lots |
| `legacy_exit_window` | `{max_resting_orders: 20, max_distance_pct: 15}` | rolling window |

## The two live gates (never bypass)

Real orders require **both**: env `ALLOW_LIVE=1` (in `.github/workflows/bot.yml`)
**AND** `strategy_config.confirm_live=true`. Additionally, while
`live_validate_only=true`, every AddOrder carries `validate=true` and executes
nothing. To stop trading instantly, set `kill_switch=true` (checked before any
order logic) — it's faster and safer than editing the workflow.

## Go-live rollout sequence that worked

The paper run (2026-07-09 → 07-21) never organically filled a rung — BTC stayed
above the top rung the whole time — so the buy→fill→sell path could not be proven
in paper. Instead we used a **validate-only smoke test**:

1. `mode=live`, gates closed → bot reconciles + snapshots, creates nothing
   (`live_gate_closed_skip_execution`). Confirms the live read path.
2. Gates open, `live_validate_only=true` → AddOrder sent with `validate=true`.
   Success signature: grid orders land in `orders` as **`canceled`** with
   `error='validate-only mode'`, `txid=None`, and **no** `order_submit_failed`
   events. Proves auth, HMAC signing, price/volume formatting, post-only flags.
3. `live_validate_only=false` → real orders rest. First real fills were legacy
   sells: **+$3.26 net across 4 lots** (200→203.26).

## Gotchas found during go-live (all fixed)

### 1. Real maker fee is 0.40%, not 0.25%
First real legacy fills netted +0.85% against a +1% target; implied fee 0.40%
(consistent with the baseline's historical sells). Fix: `fee_maker_pct=0.40`
and recompute all stored legacy targets (`python -m bot.legacy_import
--recompute-targets`). Targets are now derived from config, not hardcoded, and
`bot/legacy.py` self-corrects a resting sell that sits below its (raised) target.

### 2. `initialized` must not count terminal orders
`hydrate_strategy` originally set `initialized` from *any* order for the
strategy — including `canceled`/`failed`. After the validate-only smoke test (7
canceled rungs), the grid believed its ladder existed and placed nothing, going
permanently dormant. Fix (`bot/run.py`): `initialized` counts only **open**
orders (`pending`/`submitted`/`open`) **or** open lots. Invariant: a strategy is
"initialized" only if it has something actually working in the market.

### 3. `max_orders_per_day` must fit a full cycle's orders
The cap was 12. A single cycle can want 7 grid rungs + up to ~6 legacy
re-places, and validate-only runs also consume the daily budget. The first real
cycle hit the cap at 12 and placed only 5 of 7 rungs — and the grid has **no
top-up logic**, so a partial ladder stays partial until a recenter. Fix: raised
to 50. Keep it comfortably above `(rungs + legacy window size)`.

### 4. Legacy sells bypass the daily order cap
`bot/legacy.py` calls `execute_intents` directly, not through
`risk.filter_intents`, so legacy sells are **not** subject to
`max_orders_per_day` (or any guardrail). Acceptable — they're risk-reducing
sells, which the risk manager never vetoes anyway — but know that the cap only
bounds strategy (grid) orders.

## Known limitations / open items

- **Grid partial ladder doesn't self-heal.** If some rungs are vetoed/rejected,
  the grid won't top up the missing ones until price moves enough to trigger a
  recenter. Workaround: cancel the resting rungs so the next cycle re-lays a full
  ladder. A proper fix (place only the missing rungs) is not yet implemented.
- **Validate-only re-lays the ladder every cycle.** Because validated orders come
  back `canceled`, `initialized` stays false and the grid re-submits all rungs
  each cycle — harmless noise that accumulates `canceled` rows. Stops the moment
  `live_validate_only=false` (real rungs rest as `open`).
- **GitHub cron is best-effort** — has been firing closer to hourly than every
  15 min. For an immediate cycle, trigger the workflow manually (Actions tab →
  trading-bot → Run workflow); it exercises the deployed code + secrets.
- **Weekly summary email** (Phase 4) not yet implemented.
- **Buy→sell fill path** was first exercised with real money, not paper — watch
  the first grid rung fill (BTC ~−4% from where the ladder was laid) closely.

## Routine checks

- **Exchange vs DB consistency**: count of Kraken `OpenOrders` should equal DB
  `orders` rows in `pending`/`submitted`/`open`. A mismatch means reconciliation
  drift — investigate before the next cycle.
- **Lot ↔ order agreement**: lots in state `exiting` should each have a live
  sell order; `open` lots should not.
- **Realized P&L**: sum of closed `lots` (`proceeds_usd − cost − fees`). Cross-
  check against `equity_snapshots.realized_cum_usd`.
- **Alerts**: any `error`-severity `bot_events` row emails immediately; also
  watch for `order_submit_failed`, `partial_sell_canceled` (needs manual lot
  fix), `drawdown_guard`, `stale_market_data`.
- A read-only snapshot script pattern lives in the session scratchpad; the
  queries above are all `select`-only and safe to run anytime.

## Emergency stop

Set `strategy_config.kill_switch=true`. The next cycle exits before any order
logic (logs `kill_switch_active`). Resting orders stay on Kraken — cancel them
manually via `bot.kraken_api.cancel_order(txid)` or the Kraken UI if you also
want them pulled.
