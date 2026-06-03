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
    th.trade_id AS trade_history_id,
    buy.asset,
    th.cost AS proceeds_usd,
    buy.cost_usd AS cost_basis_usd,
    buy.fee_usd + th.fee AS fees_usd,
    th.cost - buy.cost_usd - (buy.fee_usd + th.fee) AS gain_loss_usd,
    (
        (th.cost - buy.cost_usd - (buy.fee_usd + th.fee))
        / buy.cost_usd
    ) * 100 AS gain_loss_pct,
    EXTRACT(
        DAY FROM
        TO_TIMESTAMP(th.time) - buy.executed_at
    )::int AS holding_days,
    TO_TIMESTAMP(th.time) AS closed_at
FROM trades AS buy
INNER JOIN trades_history AS th
    ON buy.order_txid = th.order_txid
WHERE
    buy.side = 'buy'
    AND buy.status = 'sold'
    AND NOT EXISTS (
        SELECT 1 FROM realized_pnl AS p
        WHERE p.buy_base_ledger_id = buy.base_ledger_id
    );
