CREATE TABLE public.realized_pnl (
    buy_base_ledger_id text NOT NULL,
    buy_quote_ledger_id text NOT NULL,
    trade_history_id text NOT NULL,
    asset text NULL,
    proceeds_usd double precision NULL,
    cost_basis_usd double precision NULL,
    fees_usd double precision NULL,
    gain_loss_usd double precision NULL,
    gain_loss_pct double precision NULL,
    holding_days integer NULL,
    closed_at timestamp without time zone NULL,
    CONSTRAINT realized_pnl_pkey PRIMARY KEY (
        buy_base_ledger_id, buy_quote_ledger_id
    ),
    CONSTRAINT fk_buy_trade FOREIGN KEY (
        buy_base_ledger_id, buy_quote_ledger_id
    ) REFERENCES trades (base_ledger_id, quote_ledger_id),
    CONSTRAINT fk_trade_history FOREIGN KEY (
        trade_history_id
    ) REFERENCES trades_history (trade_id)
) TABLESPACE pg_default;
