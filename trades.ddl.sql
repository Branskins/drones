CREATE TABLE public.trades (
    base_ledger_id text NOT NULL,
    quote_ledger_id text NOT NULL,
    asset text NULL,
    status text NULL,
    side text NULL,
    volume double precision NULL,
    price_usd double precision NULL,
    cost_usd double precision NULL,
    fee_usd double precision NULL,
    executed_at timestamp without time zone NULL,
    CONSTRAINT trades_pkey PRIMARY KEY (base_ledger_id, quote_ledger_id)
) TABLESPACE pg_default;
