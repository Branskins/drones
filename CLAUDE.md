# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

This repo has three parts that share one Supabase Postgres database:

- **Root (Python)** — a batch pipeline that pulls trading data from the Kraken exchange API and syncs it into Supabase.
- **`bot/` + `backtest/` (Python)** — an autonomous trading bot (paper/live modes, run by GitHub Actions cron) and the backtest harness that selects its strategies. Design doc: `docs/autonomous-trading-plan.md`; pending manual steps: `docs/human-actions.md`.
- **`web/`** — a Next.js 16 (App Router) dashboard that reads that data, lets a signed-in user place sell orders through Kraken, and shows bot performance at `/performance`.

The pipeline and web app are not deployed together and have no shared build tooling; treat them as separate projects that happen to live in one repo. The bot imports from the pipeline's `utils/kraken.py`.

## Python pipeline (root)

### Setup / commands

```bash
pip install -r requirements.txt

# One-time: create the Postgres functions the pipeline calls via RPC
python pipeline.py --setup

# Run the full sync pipeline (ledgers -> trades history -> reconstruct trades -> realized P&L)
python pipeline.py
```

Requires a `.env` (see `.env.example`) with `PUBLIC_KEY` / `PRIVATE_KEY` (Kraken API), `SUPABASE_URL` / `SUPABASE_KEY`, and `DATABASE_URL` (direct Postgres connection, used only for `--setup`).

`ledgers.py` and `trades_history.py` are also runnable standalone for ad-hoc use:

```bash
python ledgers.py {csv|ledger|db}
python trades_history.py {csv|trade|db}
```

There is no test suite or linter configured for the Python code.

### Architecture

- `utils/kraken.py` — low-level signed HTTP request helper for Kraken's private API (nonce, HMAC-SHA512 signing). Everything else builds on `request()`.
- `ledgers.py` / `trades_history.py` — each paginates a Kraken private endpoint (`Ledgers` / `TradesHistory`, 50 rows/page), flattens the result into a DataFrame, and upserts into the `ledgers` / `trades_history` Supabase tables (conflict key: `ledger_id` / `trade_id`). Sync is incremental: it passes Kraken's `start` param from the newest stored `time` minus a 1-day overlap.
- `pipeline.py` — orchestrates the full sync in 4 steps: sync ledgers, sync trades history, then two Postgres functions run server-side via `supabase.rpc(...)`:
  - `sync_trades` (`sql/trades.sql`) — reconstructs buy/sell trades by matching `ledgers` rows into pairs by `refid`: a base-asset leg (`XXBT`/`XETH`) with a quote-asset leg (`ZUSD`). Positive base amount = buy (status `available`), negative = sell (status `executed`).
  - `sync_realized_pnl` (`sql/realized_pnl.sql`) — joins closed (`sold`) `trades` rows against `trades_history` on `order_txid` to compute realized gain/loss and holding period.
  - `pipeline.py --setup` (re-)installs both as SQL functions in Postgres from the `.sql` files, wrapped as `CREATE OR REPLACE FUNCTION ... LANGUAGE sql`, and applies `sql/bot.ddl.sql` (idempotent) to create/seed the bot tables.
- `sql/*.ddl.sql` — reference DDL for the 4 pipeline tables (`ledgers`, `trades`, `trades_history`, `realized_pnl`); not applied automatically, kept in sync with Supabase manually. `sql/bot.ddl.sql` is the exception — it IS applied by `--setup`.
- SQL is formatted per `.sqlfluff` (postgres dialect, upper-case keywords, 4-space indent).

The trade lifecycle across tables: `ledgers` (raw Kraken ledger entries) → `trades` (reconstructed buy legs, status `available` until sold) → on sell, `web/app/actions/trades.ts` places a live Kraken order and flips status to `sold` (via an intermediate `selling` claim state that prevents double-sells) → `realized_pnl` (computed once a `trades_history` sell row exists for that `order_txid`; fills are aggregated per order to handle partial fills).

## Trading bot (`bot/`) and backtests (`backtest/`)

### Commands

```bash
python -m bot.run                    # one stateless bot cycle (what GH Actions cron runs)
python -m bot.data                   # refresh OHLC candle caches + market_data table
python -m bot.legacy_import          # (re-)import pre-bot lots with +1% net targets; prints report
python -m backtest.study             # strategy comparison sweep -> docs/strategy-study.md
python -m backtest.validate_baseline # accounting validation gate vs real realized_pnl rows
```

### Architecture

- **Modes** (`strategy_config` table, key `mode`): `off` | `paper` | `live`. Paper mode records orders in the `orders` table and fills them against the public ticker (`bot/executor.py:reconcile_paper`) — it never calls Kraken's private API. Live mode is double-gated: env `ALLOW_LIVE=1` AND config `confirm_live=true`; additionally `live_validate_only` (default true) sends AddOrder with `validate=true`. Live reconciliation is NOT yet implemented (Phase 5) — `bot/run.py` refuses to run live.
- **Cycle** (`bot/run.py`, stateless — all state in Supabase): refresh candles → hydrate strategy state from DB → reconcile fills (fill hooks rest the paired sell / re-arm grid rungs) → guardrails (`bot/risk.py`: budget cap, max lots, orders/day, drawdown, data freshness; sells are never vetoed) → strategy decision → execute → snapshot + email alerts (`bot/monitor.py`, `bot/notify.py`, needs `SMTP_APP_PASSWORD`).
- **Strategies** (`bot/strategies.py`): `dca_tp` (fixed-cadence DCA + net take-profit), `dca_dip` (SMA-tiered dip buying, inventory recycling, optional drawdown stop), `grid` (static rung ladder). One implementation serves both backtest (`backtest/engine.py` drives `on_candle`/fill hooks per candle) and the live cycle (hydrated from DB, driven by ticker). Take-profit targets are NET of fees (`Lot.target_for_net_gain`).
- **Accounting** (`bot/models.py`): `Portfolio`/`Lot` are the single accounting implementation shared by backtest and production; `backtest/validate_baseline.py` must pass (reproduces the real account's `realized_pnl` to the cent) before trusting any backtest change.
- **Tables** (`sql/bot.ddl.sql`): `orders` (state machine: pending→submitted/open→filled|canceled|failed), `lots` (open→exiting→closed; `strategy='legacy'` rows are the 78 pre-bot lots awaiting +1% net exit), `market_data` (candles), `strategy_config` (jsonb key/value, editable knobs), `equity_snapshots`, `bot_events` (structured log; error severity triggers email).
- **Scheduling**: `.github/workflows/bot.yml`, 15-min cron with a concurrency group. Secrets required — see `docs/human-actions.md`.
- Candle caches live in `backtest/data/*.csv` (~2 years of daily candles from the public API; deeper history is a documented manual download).

## Web app (`web/`)

### Commands

```bash
cd web
npm run dev     # start dev server (localhost:3000)
npm run build
npm run start
npm run lint     # eslint
```

Requires `web/.env.local` (see `.env.local.example`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (browser-safe, RLS-protected), plus `PUBLIC_KEY` / `PRIVATE_KEY` (Kraken, server-only — used to place live orders). No test suite is configured.

### Architecture

- **Auth**: Supabase email/password auth gates the whole app. `proxy.ts` (Next's middleware-equivalent, renamed `proxy` per the current Next.js convention) runs `updateSession()` (`lib/supabase/proxy.ts`) on every request except static assets, refreshes the session, and redirects any unauthenticated request to `/login` unless the path starts with `/login` or `/auth`. There are three separate Supabase client constructors, each for a different execution context — always use the matching one:
  - `lib/supabase/client.ts` — browser (Client Components, e.g. the login form).
  - `lib/supabase/server.ts` — Server Components / Route Handlers / Server Actions (cookie read/write via `next/headers`).
  - `lib/supabase/proxy.ts` — the proxy/middleware request-response cycle (cookie read/write via the `NextRequest`/`NextResponse` pair).
- **Data flow**: `app/page.tsx` → `components/ledger.tsx` (Server Component) queries `trades` directly via Supabase (open, unsold BTC/ETH trades) and renders `components/ticker.tsx` + `components/ledger-table.tsx` (both Client Components). `app/performance/page.tsx` (Server Component) renders the bot's equity snapshots, open lots/orders, legacy lot aging, and recent events.
- **Kraken integration** (`lib/kraken.ts`, server-only — signs requests with `PUBLIC_KEY`/`PRIVATE_KEY`):
  - `fetchPriceData()` — public ticker for BTC/ETH, cached 30s (`next: { revalidate: 30 }`), exposed to the client via `app/api/ticker/route.ts` and polled every 30s from `ticker.tsx`/`ledger-table.tsx`.
  - `addOrder()` — places a live market order. Invoked only from `app/actions/trades.ts`'s `markTradeAsSold` Server Action: looks up the trade, maps its asset to a Kraken pair (`XXBT`→`XBTUSD`, `XETH`→`ETHUSD`), places a **real market sell order**, then updates the `trades` row to `status: 'sold'` with the returned `order_txid`. Be careful modifying this path — it executes real trades against a live Kraken account, not a sandbox.
  - P&L shown in `ledger-table.tsx` is computed client-side against the live bid price polled from `/api/ticker`, separately from the server-side `realized_pnl` table populated by the Python pipeline.
