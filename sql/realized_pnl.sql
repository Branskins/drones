WITH order_fills AS (
    -- An order can fill across multiple trades (partial fills); aggregate
    -- per order so each buy lot joins exactly one row with full proceeds.
    SELECT
        order_txid,
        SUM(cost) AS proceeds_usd,
        SUM(fee) AS fee_usd,
        MIN(time) AS closed_time
    FROM trades_history
    GROUP BY order_txid
)

INSERT INTO realized_pnl (
    buy_base_ledger_id,
    buy_quote_ledger_id,
    trade_history_id,
    asset,
    proceeds_usd,
    cost_basis_usd,
    fees_usd,
    gain_loss_usd,
    gain_loss_pct,
    holding_days,
    closed_at
)

SELECT
    buy.base_ledger_id AS buy_base_ledger_id,
    buy.quote_ledger_id AS buy_quote_ledger_id,
    (
        SELECT th.trade_id FROM trades_history AS th
        WHERE th.order_txid = fills.order_txid
        ORDER BY th.time ASC
        LIMIT 1
    ) AS trade_history_id,
    buy.asset,
    fills.proceeds_usd,
    buy.cost_usd AS cost_basis_usd,
    buy.fee_usd + fills.fee_usd AS fees_usd,
    fills.proceeds_usd - buy.cost_usd - (buy.fee_usd + fills.fee_usd) AS gain_loss_usd,
    (
        (fills.proceeds_usd - buy.cost_usd - (buy.fee_usd + fills.fee_usd))
        / buy.cost_usd
    ) * 100 AS gain_loss_pct,
    EXTRACT(
        DAY FROM
        TO_TIMESTAMP(fills.closed_time) - buy.executed_at
    )::int AS holding_days,
    TO_TIMESTAMP(fills.closed_time) AS closed_at
FROM trades AS buy
INNER JOIN order_fills AS fills
    ON buy.order_txid = fills.order_txid
WHERE
    buy.side = 'buy'
    AND buy.status = 'sold'
    AND NOT EXISTS (
        SELECT 1 FROM realized_pnl AS p
        WHERE p.buy_base_ledger_id = buy.base_ledger_id
    );
