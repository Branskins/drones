-- Bot infrastructure tables (applied idempotently by `python pipeline.py --setup`).
-- Money/volume columns use NUMERIC (not double precision) on purpose.

CREATE TABLE IF NOT EXISTS public.orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('paper', 'live')),
    strategy text NOT NULL,
    pair text NOT NULL,
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    ordertype text NOT NULL CHECK (ordertype IN ('limit', 'market')),
    price numeric NULL,
    volume numeric NOT NULL,
    userref integer NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (
        state IN ('pending', 'submitted', 'open', 'filled', 'canceled', 'failed')
    ),
    kraken_txid text NULL,
    lot_id bigint NULL,
    reason text NULL,
    filled_volume numeric NULL,
    avg_fill_price numeric NULL,
    fee_usd numeric NULL,
    error text NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NULL
);

CREATE INDEX IF NOT EXISTS orders_state_idx ON public.orders (state);
CREATE INDEX IF NOT EXISTS orders_mode_strategy_idx ON public.orders (mode, strategy);

CREATE TABLE IF NOT EXISTS public.lots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('paper', 'live')),
    strategy text NOT NULL,
    asset text NOT NULL,
    volume numeric NOT NULL,
    cost_usd numeric NOT NULL,
    fee_usd numeric NOT NULL DEFAULT 0,
    buy_order_id bigint NULL REFERENCES public.orders (id),
    sell_order_id bigint NULL REFERENCES public.orders (id),
    base_ledger_id text NULL,      -- linkage for legacy lots imported from trades
    target_price numeric NULL,
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'exiting', 'closed')),
    opened_at timestamptz NULL,
    closed_at timestamptz NULL,
    proceeds_usd numeric NULL
);

CREATE INDEX IF NOT EXISTS lots_mode_state_idx ON public.lots (mode, state);
CREATE UNIQUE INDEX IF NOT EXISTS lots_base_ledger_idx
    ON public.lots (base_ledger_id) WHERE base_ledger_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.market_data (
    pair text NOT NULL,
    interval_min integer NOT NULL,
    ts timestamptz NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    PRIMARY KEY (pair, interval_min, ts)
);

CREATE TABLE IF NOT EXISTS public.strategy_config (
    key text PRIMARY KEY,
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.equity_snapshots (
    ts timestamptz NOT NULL,
    mode text NOT NULL CHECK (mode IN ('paper', 'live')),
    cash_usd numeric NOT NULL,
    inventory_value_usd numeric NOT NULL,
    unrealized_usd numeric NOT NULL,
    realized_cum_usd numeric NOT NULL,
    fees_cum_usd numeric NOT NULL,
    open_lots integer NOT NULL,
    PRIMARY KEY (ts, mode)
);

CREATE TABLE IF NOT EXISTS public.bot_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts timestamptz NOT NULL DEFAULT NOW(),
    severity text NOT NULL CHECK (severity IN ('info', 'warn', 'error')),
    kind text NOT NULL,
    detail jsonb NULL
);

CREATE INDEX IF NOT EXISTS bot_events_ts_idx ON public.bot_events (ts DESC);

-- Default config (INSERT ... ON CONFLICT DO NOTHING keeps user edits).
INSERT INTO public.strategy_config (key, value) VALUES
('mode', '"off"'),
('kill_switch', 'false'),
('confirm_live', 'false'),
('live_validate_only', 'true'),
('active_strategy', '"dca_tp"'),
('budget_usd', '500'),
('batch_usd', '50'),
('max_open_lots', '10'),
('max_orders_per_day', '12'),
('max_drawdown_pct', '25'),
('fee_maker_pct', '0.25'),
('fee_taker_pct', '0.40'),
('legacy_min_gain_pct', '1.0'),
('legacy_exit_window', '{"max_resting_orders": 20, "max_distance_pct": 15}'),
('dca_tp', '{"interval_hours": 72, "tp_pct": 4.0}'),
('dca_dip', '{"interval_hours": 72, "tp_pct": 4.0, "sma_days": 30, "tiers": [[0.05, 0], [0.0, 1], [-0.05, 2], [-0.15, 3]], "max_age_days": 45}'),
('grid', '{"band_pct": 25, "step_pct": 4.0, "recenter_pct": 10}')
ON CONFLICT (key) DO NOTHING;
