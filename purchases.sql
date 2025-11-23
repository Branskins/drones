WITH transactions AS (
    SELECT
        CASE
            WHEN type = 'spend' THEN -amount
            ELSE amount
        END AS amount,
        asset,
        refid
    FROM ledgers
    WHERE type IN ('receive', 'spend')
),

non_zusd_df AS (
    SELECT *
    FROM transactions
    WHERE asset != 'ZUSD'
),

zusd_df AS (
    SELECT *
    FROM transactions
    WHERE asset = 'ZUSD'
)

SELECT
    z.refid,
    z.amount AS amount_zusd,
    n.amount AS amount_non_zusd,
    n.asset,
    z.amount / n.amount AS purchase_price
FROM zusd_df z
LEFT JOIN non_zusd_df n ON z.refid = n.refid;
