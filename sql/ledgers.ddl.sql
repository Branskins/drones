CREATE TABLE public.ledgers (
    ledger_id text NOT NULL,
    amount double precision NULL,
    asset text NULL,
    balance double precision NULL,
    fee double precision NULL,
    refid text NULL,
    time bigint NULL,
    type text NULL,
    CONSTRAINT ledgers_pkey PRIMARY KEY (ledger_id)
) TABLESPACE pg_default;
