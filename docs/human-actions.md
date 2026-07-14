# Human actions required

Things the autonomous implementation could not do itself. Ordered by phase;
nothing in the paper phase is blocked — items 1–4 unlock alerts + CI, items
5–7 gate real money.

## To activate the scheduled paper bot (Phase 3/4)

1. **Add GitHub Actions secrets** (repo → Settings → Secrets and variables → Actions):
   - `SUPABASE_URL`, `SUPABASE_KEY` — same values as the root `.env`.
   - `SMTP_APP_PASSWORD` — Gmail app password (Google Account → Security →
     2-Step Verification → App passwords). Used by `bot/notify.py` for alert emails.
   - `ALERT_EMAIL` — optional; defaults to andresjelizondo@gmail.com.
   - `KRAKEN_BOT_PUBLIC_KEY` / `KRAKEN_BOT_PRIVATE_KEY` — see item 5; not needed
     while paper mode is the only thing running, but the workflow references them.
2. **Push the repo to GitHub** (the workflow `.github/workflows/bot.yml` activates on
   push). The cron runs every 15 min; paper mode makes no private Kraken calls.
   - The bot is currently configured `mode=paper`, `active_strategy=grid`,
     `pair=XBTUSD` (per the strategy study). Change via the `strategy_config` table.
3. **Verify the first scheduled run** in the Actions tab, then check
   `equity_snapshots` / `bot_events` rows are appearing.

## Data quality (recommended before trusting the study)

4. **Download Kraken's historical OHLCVT archive** (support.kraken.com → "Downloadable
   historical OHLCVT data") for XBTUSD and ETHUSD. Convert to the cache layout
   (`ts,open,high,low,close,volume` CSV) and merge into `backtest/data/XBTUSD_1440.csv` /
   `ETHUSD_1440.csv`, then re-run `python -m backtest.study`. The current study only
   covers ~2 years (public API limit of 720 candles) and misses the 2021–2023 cycle.

## To go live (Phase 5 — deliberately manual)

5. **Create a bot-dedicated Kraken API key** with permissions: Query Funds,
   Query Open/Closed Orders & Trades, Create & Modify Orders, Cancel Orders.
   **No Withdraw Funds. No Export Data.** Store as the two `KRAKEN_BOT_*` secrets.
   (Separate key from the web app's, so nonces never collide — see F10 in the plan.)
6. **Fund/verify prerequisites**: switch deposits to ACH/wire (card deposits cost
   3.8% — $190 on the $5k baseline); confirm account tier's max open orders
   (needed for the legacy rolling window + grid rungs).
7. **Open the live gate** — BOTH must be set, by a human:
   - `strategy_config`: `confirm_live` = `true`, and `live_validate_only` = `false`
     (until then AddOrder is called with `validate=true` and executes nothing).
   - GitHub Actions workflow env: add `ALLOW_LIVE: "1"`.
   Acceptance criteria before doing this (from the plan): ≥2 weeks of unattended
   paper running with zero unreconciled orders, paper equity tracking backtest
   expectation.
   ~~Also required first: implement live reconciliation~~ **Done (2026-07-14)**:
   `bot/executor.py:reconcile_live` tracks live orders via QueryOrders, recovers
   crashed `pending` orders by userref lookup, and handles partial fills
   (partial *sells* canceled mid-fill raise an error event for manual lot
   adjustment). With `mode=live` and the gate closed, the bot reconciles and
   snapshots but skips order creation (`live_gate_closed_skip_execution` warn).
   Suggested rollout: set `mode=live` with `live_validate_only=true` for a few
   days first — AddOrder is exercised end-to-end (auth, formatting, funds
   checks) without a single order executing.

## Legacy lots (Phase 6)

8. The 78 pre-bot lots are imported into `lots` (strategy `legacy`) with +1% net
   targets (`python -m bot.legacy_import` — re-runnable, idempotent, prints the
   rolling-window report). As of 2026-07-09, 9 lots sit inside the 15% placement
   window (nearest: BTC target $64,732, +3.1% from market).
   **Implemented (2026-07-14)**: `bot/legacy.py` runs every live cycle and
   maintains the rolling window automatically — resting GTC post-only sells for
   the `max_resting_orders` lots nearest their targets (within
   `max_distance_pct`), canceling sells that drift out of the window. It
   activates only when the Phase 5 gate is open AND `live_validate_only` is
   false; no separate step needed.

## Open decisions

9. Whether monitoring should report staking yield (BABY / ETH staking ledger rows)
   as a passive-income line (left out of scope for now).
10. Review and commit the changes on `main` — nothing has been committed; see the
    session summary for the file list.
