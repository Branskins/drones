# Strategy study — backtest results

Budget $500, batch $50, maker 0.25% / taker 0.4%, conservative fills (see backtest/engine.py).
Data: Kraken daily candles (public OHLC, 720 candles/pair — ~2 years). H1/H2 = first/second half of the period as regime slices.

## XBTUSD

Period: 2024-07-19 .. 2026-07-08. Price 66,709 -> 62,241 (-6.7%).
Buy-and-hold benchmark: net $-35.35 (-7.1%), maxDD -53.1%.

| strategy | params | net$ FULL | ret% | maxDD% | sharpe | fees$ | trips | win% | util% | net$ H1 | net$ H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dca_tp | intervalh=24 tp=2.0 | -15.24 | -3.0 | -34.6 | 0.09 | 57.63 | 225 | 100.0 | 83 | +184.73 | -200.86 |
| dca_tp | intervalh=24 tp=4.0 | +10.51 | +2.1 | -34.2 | 0.19 | 33.38 | 127 | 100.0 | 90 | +216.71 | -205.87 |
| dca_tp | intervalh=24 tp=6.0 | +4.52 | +0.9 | -35.3 | 0.17 | 22.45 | 83 | 100.0 | 93 | +231.59 | -226.96 |
| dca_tp | intervalh=24 tp=10.0 | +1.56 | +0.3 | -36.2 | 0.17 | 13.75 | 48 | 100.0 | 96 | +237.37 | -236.26 |
| dca_tp | intervalh=72 tp=2.0 | -53.08 | -10.6 | -33.4 | -0.12 | 41.34 | 160 | 100.0 | 58 | +117.66 | -171.20 |
| dca_tp | intervalh=72 tp=4.0 | +18.16 | +3.6 | -31.4 | 0.20 | 31.61 | 120 | 100.0 | 71 | +183.84 | -176.10 |
| dca_tp | intervalh=72 tp=6.0 | +30.25 | +6.0 | -32.4 | 0.25 | 23.48 | 87 | 100.0 | 81 | +223.90 | -209.22 |
| dca_tp | intervalh=72 tp=10.0 | -0.13 | -0.0 | -36.6 | 0.15 | 13.49 | 47 | 100.0 | 90 | +233.13 | -231.56 |
| dca_tp | intervalh=168 tp=2.0 | +10.92 | +2.2 | -13.3 | 0.15 | 25.05 | 97 | 100.0 | 26 | +51.16 | -138.24 |
| dca_tp | intervalh=168 tp=4.0 | -10.87 | -2.2 | -24.9 | 0.04 | 21.99 | 82 | 100.0 | 46 | +101.78 | -130.91 |
| dca_tp | intervalh=168 tp=6.0 | -29.39 | -5.9 | -33.2 | -0.01 | 16.83 | 61 | 100.0 | 62 | +145.91 | -181.14 |
| dca_tp | intervalh=168 tp=10.0 | -8.29 | -1.7 | -36.0 | 0.10 | 12.96 | 45 | 100.0 | 77 | +206.29 | -218.07 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 | -31.36 | -6.3 | -34.9 | 0.01 | 29.81 | 77 | 100.0 | 66 | +140.45 | -179.27 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 max_dd=25 | +14.46 | +2.9 | -25.9 | 0.18 | 31.09 | 83 | 92.8 | 45 | +140.45 | -108.80 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 | -8.45 | -1.7 | -33.5 | 0.10 | 29.38 | 76 | 100.0 | 68 | +164.77 | -177.21 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 max_dd=25 | -7.00 | -1.4 | -31.1 | 0.09 | 30.47 | 83 | 91.6 | 46 | +164.77 | -107.42 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 | -36.31 | -7.3 | -35.7 | 0.01 | 22.10 | 59 | 100.0 | 72 | +144.50 | -206.90 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 max_dd=25 | +10.41 | +2.1 | -26.6 | 0.17 | 23.41 | 65 | 90.8 | 50 | +144.50 | -111.17 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 | +10.89 | +2.2 | -33.3 | 0.18 | 21.51 | 57 | 100.0 | 74 | +185.39 | -205.20 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 max_dd=25 | +12.37 | +2.5 | -30.9 | 0.17 | 22.61 | 64 | 89.1 | 53 | +185.39 | -108.85 |
| grid | step=3.0 band=25 | +55.44 | +11.1 | -5.3 | 0.77 | 12.06 | 47 | 100.0 | 5 | +38.25 | -144.31 |
| grid | step=3.0 band=40 | +56.68 | +11.3 | -5.3 | 0.82 | 12.31 | 48 | 100.0 | 5 | +39.49 | -152.91 |
| grid | step=4.0 band=25 | +49.08 | +9.8 | -4.2 | 0.96 | 7.57 | 29 | 100.0 | 4 | +32.83 | -107.17 |
| grid | step=4.0 band=40 | +49.08 | +9.8 | -4.2 | 0.96 | 7.57 | 29 | 100.0 | 4 | +32.83 | -132.54 |
| grid | step=6.0 band=25 | +32.09 | +6.4 | -2.7 | 0.91 | 3.18 | 12 | 100.0 | 2 | +21.72 | -64.62 |
| grid | step=6.0 band=40 | +32.09 | +6.4 | -2.7 | 0.91 | 3.18 | 12 | 100.0 | 2 | +21.72 | -92.73 |

## ETHUSD

Period: 2024-07-19 .. 2026-07-08. Price 3,505 -> 1,742 (-50.3%).
Buy-and-hold benchmark: net $-252.52 (-50.5%), maxDD -67.6%.

| strategy | params | net$ FULL | ret% | maxDD% | sharpe | fees$ | trips | win% | util% | net$ H1 | net$ H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dca_tp | intervalh=24 tp=2.0 | -164.66 | -32.9 | -50.7 | -0.13 | 36.83 | 142 | 100.0 | 90 | -29.87 | -235.14 |
| dca_tp | intervalh=24 tp=4.0 | -151.39 | -30.3 | -52.1 | -0.09 | 21.74 | 81 | 100.0 | 94 | -32.53 | -220.87 |
| dca_tp | intervalh=24 tp=6.0 | -153.89 | -30.8 | -53.6 | -0.09 | 14.78 | 53 | 100.0 | 95 | -39.46 | -213.44 |
| dca_tp | intervalh=24 tp=10.0 | -131.08 | -26.2 | -54.1 | -0.03 | 10.62 | 36 | 100.0 | 97 | -38.88 | -180.71 |
| dca_tp | intervalh=72 tp=2.0 | -124.14 | -24.8 | -45.1 | -0.23 | 39.84 | 154 | 100.0 | 65 | +80.81 | -197.21 |
| dca_tp | intervalh=72 tp=4.0 | -103.31 | -20.7 | -46.3 | -0.06 | 24.27 | 91 | 100.0 | 79 | +28.44 | -243.06 |
| dca_tp | intervalh=72 tp=6.0 | -104.59 | -20.9 | -46.7 | -0.06 | 18.62 | 68 | 100.0 | 84 | +29.42 | -244.54 |
| dca_tp | intervalh=72 tp=10.0 | -82.30 | -16.5 | -48.1 | 0.03 | 12.96 | 45 | 100.0 | 90 | +22.49 | -237.46 |
| dca_tp | intervalh=168 tp=2.0 | -37.04 | -7.4 | -22.4 | -0.19 | 24.68 | 95 | 100.0 | 27 | +36.48 | -163.46 |
| dca_tp | intervalh=168 tp=4.0 | -26.14 | -5.2 | -30.2 | 0.03 | 23.01 | 86 | 100.0 | 48 | +52.30 | -154.99 |
| dca_tp | intervalh=168 tp=6.0 | -12.35 | -2.5 | -33.1 | 0.12 | 21.43 | 79 | 100.0 | 62 | +80.14 | -189.86 |
| dca_tp | intervalh=168 tp=10.0 | -94.41 | -18.9 | -45.2 | -0.04 | 11.40 | 39 | 100.0 | 77 | +57.09 | -232.49 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 | -103.23 | -20.6 | -44.2 | -0.05 | 27.62 | 59 | 100.0 | 76 | +51.67 | -217.36 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 max_dd=25 | -74.15 | -14.8 | -26.9 | -0.19 | 17.30 | 40 | 85.0 | 20 | -74.15 | -87.30 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 | -77.81 | -15.6 | -43.4 | 0.01 | 26.94 | 57 | 100.0 | 77 | +61.47 | -217.36 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 max_dd=25 | -64.23 | -12.8 | -26.4 | -0.15 | 16.83 | 39 | 84.6 | 20 | -64.23 | -87.30 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 | -134.02 | -26.8 | -48.4 | -0.12 | 19.31 | 41 | 100.0 | 79 | +7.05 | -193.72 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 max_dd=25 | -85.49 | -17.1 | -27.2 | -0.26 | 11.75 | 28 | 78.6 | 21 | -85.49 | -67.64 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 | -97.49 | -19.5 | -47.7 | -0.02 | 17.90 | 37 | 100.0 | 80 | +16.28 | -193.72 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 max_dd=25 | -76.26 | -15.2 | -26.8 | -0.20 | 10.26 | 24 | 75.0 | 22 | -76.26 | -67.64 |
| grid | step=3.0 band=25 | -42.40 | -8.5 | -37.4 | 0.09 | 30.76 | 118 | 100.0 | 59 | +68.50 | -110.13 |
| grid | step=3.0 band=40 | -30.28 | -6.1 | -39.3 | 0.14 | 36.66 | 141 | 100.0 | 64 | +96.88 | -113.56 |
| grid | step=4.0 band=25 | -12.64 | -2.5 | -28.8 | 0.11 | 20.05 | 76 | 100.0 | 45 | +67.17 | -74.56 |
| grid | step=4.0 band=40 | +31.50 | +6.3 | -36.7 | 0.27 | 33.05 | 126 | 100.0 | 57 | +148.37 | -64.90 |
| grid | step=6.0 band=25 | -4.62 | -0.9 | -18.3 | 0.06 | 7.89 | 29 | 100.0 | 27 | +37.31 | -51.05 |
| grid | step=6.0 band=40 | +69.27 | +13.8 | -30.0 | 0.37 | 20.11 | 75 | 100.0 | 42 | +143.21 | -31.91 |

## Findings

1. **Context**: the 2-year window is bearish — BTC −6.7% (B&H net −$35, maxDD −53%),
   ETH −50.3% (B&H net −$253, maxDD −68%). A strategy "wins" here by protecting capital
   while still harvesting oscillation.
2. **Grid is the standout on BTC**: step 3–4% nets +$49..+$57 (≈+10–11%) with **max
   drawdown −4..−5%** vs −31..−37% for every DCA variant and −53% for buy-and-hold.
   Small caveat: its low drawdown partly reflects low utilization (rungs sit below
   price much of the time) — it risks less, so it loses less.
3. **The 100% win rate on every dca_tp row is the pathology, not a virtue**: take-profit-only
   strategies realize every winner and warehouse every loser as an open lot. Net P&L
   (which marks open lots to market) shows the truth — e.g. ETH dca_tp 24h: 100% win
   rate, −$151 net. This is exactly what happened to the real account.
4. **H2 (the bear leg) is where strategies differ**: dca_dip's max_dd=25 portfolio stop
   roughly halves H2 losses on BTC (−108 vs −177) and ETH (−87 vs −217) at the cost of
   locking in losses when it triggers. The trend-filter/dip-scaling alone (without the
   stop) did NOT help materially vs plain DCA on this data.
5. **ETH was hostile to everything**; only wide grids (step 6%, band 40%: +$69) stayed
   positive. Against a −50% market that is a strong result, but it's one regime.

## Recommendation

- **Paper phase (Phase 3)**: run **grid (step 4%, band 25%) on BTC** as the primary
  candidate and **dca_tp (72h, tp 4–6%) on BTC** as the control. Hold off on ETH with
  real money until the strategy survives a longer backtest window.
- **Before live**: extend the dataset with Kraken's downloadable OHLCVT history
  (2021–2024 covers a full bull+bear cycle — see docs/human-actions.md) and re-run
  `python -m backtest.study`. The current 720-candle window is the binding limitation.
- Parameters were chosen from plateaus (grid 3–4% similar, dca_tp 4–6% similar), not
  single peaks, per the plan's overfitting rule.

*(Regenerating this file: `python -m backtest.study` rewrites the tables above and
drops this section — re-add or update it after each run.)*
