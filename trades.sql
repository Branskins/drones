WITH base_legs AS (
  SELECT *
  FROM ledgers
  WHERE asset IN ('XXBT', 'XETH')
),

quote_legs AS (
  SELECT *
  FROM ledgers
  WHERE asset = 'ZUSD'
),

trade_pairs AS (
  SELECT
    base.ledger_id                                    AS base_ledger_id,
    quote.ledger_id                                   AS quote_ledger_id,
    base.asset                                 AS asset,
    CASE WHEN base.amount > 0
      THEN 'buy'
      ELSE 'sell'
    END                                        AS side,
    ABS(base.amount)                           AS volume,
    ABS(quote.amount) / ABS(base.amount)       AS price_usd,
    ABS(quote.amount)                          AS cost_usd,
    ABS(base.fee) + ABS(quote.fee)             AS fee_usd,
    CASE WHEN base.amount > 0
      THEN 'available'
      ELSE 'executed'
    END                                        AS status,
    TO_TIMESTAMP(base.time)                    AS executed_at
  FROM base_legs base
  JOIN quote_legs quote
    ON base.refid = quote.refid
)

INSERT INTO trades (
  base_ledger_id,
  quote_ledger_id,
  asset,
  side,
  volume,
  price_usd,
  cost_usd,
  fee_usd,
  status,
  executed_at
)
SELECT
  base_ledger_id,
  quote_ledger_id,
  asset,
  side,
  volume,
  price_usd,
  cost_usd,
  fee_usd,
  status,
  executed_at
FROM trade_pairs
WHERE NOT EXISTS (
  SELECT 1 FROM trades t
  WHERE t.base_ledger_id = trade_pairs.base_ledger_id
);