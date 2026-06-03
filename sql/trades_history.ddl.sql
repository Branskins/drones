CREATE TABLE public.trades_history (
    trade_id text NOT NULL,
    order_txid text NULL,
    pair text NULL,
    type text NULL,
    price double precision NULL,
    cost double precision NULL,
    fee double precision NULL,
    vol double precision NULL,
    time double precision NULL,
    CONSTRAINT trades_history_pkey PRIMARY KEY (trade_id)
) TABLESPACE pg_default;
