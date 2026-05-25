create table public.trades (
  base_ledger_id text not null,
  quote_ledger_id text not null,
  asset text null,
  status text null,
  side text null,
  volume double precision null,
  price_usd double precision null,
  cost_usd double precision null,
  fee_usd double precision null,
  executed_at timestamp without time zone null,
  constraint trades_pkey primary key (base_ledger_id, quote_ledger_id)
) TABLESPACE pg_default;