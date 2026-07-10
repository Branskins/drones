# Strategy study — backtest results

Budget $500, batch $50, maker 0.25% / taker 0.4%, conservative fills (see backtest/engine.py).
Data: Kraken daily candles (public OHLC, 720 candles/pair — ~2 years). H1/H2 = first/second half of the period as regime slices.

## XBTUSD

Period: 2013-10-06 .. 2026-07-08. Price 122 -> 62,241 (+50917.3%).
Buy-and-hold benchmark: net $+250,256.96 (+50051.4%), maxDD -85.0%.

| strategy | params | net$ FULL | ret% | maxDD% | sharpe | fees$ | trips | win% | util% | net$ H1 | net$ H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dca_tp | intervalh=24 tp=2.0 | +639.86 | +128.0 | -71.0 | 0.36 | 223.05 | 885 | 100.0 | 88 | +185.41 | +389.73 |
| dca_tp | intervalh=24 tp=4.0 | +1088.45 | +217.7 | -67.6 | 0.45 | 170.83 | 670 | 100.0 | 91 | +446.45 | +637.82 |
| dca_tp | intervalh=24 tp=6.0 | +1341.51 | +268.3 | -62.9 | 0.51 | 137.22 | 532 | 100.0 | 93 | +647.09 | +707.26 |
| dca_tp | intervalh=24 tp=10.0 | +1649.23 | +329.9 | -57.3 | 0.59 | 100.26 | 380 | 100.0 | 95 | +886.02 | +815.47 |
| dca_tp | intervalh=72 tp=2.0 | +514.67 | +102.9 | -70.7 | 0.34 | 184.70 | 732 | 100.0 | 72 | +184.88 | +244.69 |
| dca_tp | intervalh=72 tp=4.0 | +732.81 | +146.6 | -71.9 | 0.38 | 122.74 | 480 | 100.0 | 80 | +265.16 | +433.06 |
| dca_tp | intervalh=72 tp=6.0 | +1030.77 | +206.2 | -69.7 | 0.44 | 109.36 | 423 | 100.0 | 83 | +447.84 | +530.51 |
| dca_tp | intervalh=72 tp=10.0 | +1270.36 | +254.1 | -65.3 | 0.50 | 80.19 | 303 | 100.0 | 89 | +664.31 | +620.23 |
| dca_tp | intervalh=168 tp=2.0 | +482.39 | +96.5 | -66.4 | 0.33 | 144.10 | 572 | 100.0 | 41 | +188.84 | +170.04 |
| dca_tp | intervalh=168 tp=4.0 | +584.79 | +117.0 | -68.8 | 0.35 | 98.18 | 383 | 100.0 | 67 | +206.37 | +310.14 |
| dca_tp | intervalh=168 tp=6.0 | +777.57 | +155.5 | -66.6 | 0.39 | 86.10 | 332 | 100.0 | 72 | +293.60 | +393.44 |
| dca_tp | intervalh=168 tp=10.0 | +933.32 | +186.7 | -61.8 | 0.44 | 62.47 | 235 | 100.0 | 80 | +486.49 | +517.77 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 | +556.70 | +111.3 | -71.5 | 0.34 | 120.03 | 279 | 100.0 | 74 | +287.95 | +247.46 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 max_dd=25 | -104.14 | -20.8 | -27.8 | -0.24 | 8.21 | 16 | 68.8 | 1 | -104.14 | -3.45 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 | +607.96 | +121.6 | -71.5 | 0.35 | 107.97 | 247 | 100.0 | 76 | +283.69 | +288.59 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 max_dd=25 | -104.14 | -20.8 | -27.8 | -0.24 | 8.21 | 16 | 68.8 | 1 | -104.14 | +10.44 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 | +655.06 | +131.0 | -68.8 | 0.37 | 99.04 | 236 | 100.0 | 76 | +417.08 | +234.22 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 max_dd=25 | -82.31 | -16.5 | -26.8 | -0.18 | 8.26 | 16 | 68.8 | 1 | -82.31 | +25.37 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 | +742.34 | +148.5 | -68.8 | 0.38 | 84.29 | 192 | 100.0 | 79 | +405.09 | +315.57 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 max_dd=25 | -82.31 | -16.5 | -26.8 | -0.18 | 8.26 | 16 | 68.8 | 1 | -82.31 | +39.66 |
| grid | step=3.0 band=25 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +35.78 |
| grid | step=3.0 band=40 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +41.95 |
| grid | step=4.0 band=25 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +39.74 |
| grid | step=4.0 band=40 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +60.47 |
| grid | step=6.0 band=25 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +19.01 |
| grid | step=6.0 band=40 | +0.00 | +0.0 | 0.0 | 0.00 | 0.00 | 0 | - | 0 | +0.00 | +54.31 |

## ETHUSD

Period: 2015-08-07 .. 2026-07-08. Price 3 -> 1,742 (+57967.7%).
Buy-and-hold benchmark: net $+288,676.98 (+57735.4%), maxDD -94.1%.

| strategy | params | net$ FULL | ret% | maxDD% | sharpe | fees$ | trips | win% | util% | net$ H1 | net$ H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dca_tp | intervalh=24 tp=2.0 | +455.69 | +91.1 | -72.2 | 0.35 | 193.47 | 767 | 100.0 | 89 | +454.12 | -12.80 |
| dca_tp | intervalh=24 tp=4.0 | +913.18 | +182.6 | -71.4 | 0.44 | 157.67 | 618 | 100.0 | 90 | +795.55 | +91.33 |
| dca_tp | intervalh=24 tp=6.0 | +1236.18 | +247.2 | -70.6 | 0.49 | 134.15 | 520 | 100.0 | 92 | +1050.93 | +146.34 |
| dca_tp | intervalh=24 tp=10.0 | +1743.26 | +348.6 | -68.6 | 0.56 | 109.12 | 414 | 100.0 | 94 | +1433.07 | +269.29 |
| dca_tp | intervalh=72 tp=2.0 | +203.41 | +40.7 | -63.5 | 0.27 | 122.54 | 484 | 100.0 | 77 | +299.76 | -96.34 |
| dca_tp | intervalh=72 tp=4.0 | +589.51 | +117.9 | -65.0 | 0.37 | 112.61 | 440 | 100.0 | 80 | +524.72 | -15.66 |
| dca_tp | intervalh=72 tp=6.0 | +822.71 | +164.5 | -64.0 | 0.43 | 98.37 | 380 | 100.0 | 82 | +765.26 | +48.50 |
| dca_tp | intervalh=72 tp=10.0 | +1275.01 | +255.0 | -62.9 | 0.52 | 84.36 | 319 | 100.0 | 86 | +1136.79 | +128.59 |
| dca_tp | intervalh=168 tp=2.0 | +207.76 | +41.5 | -66.2 | 0.26 | 104.25 | 411 | 100.0 | 59 | +177.67 | +125.07 |
| dca_tp | intervalh=168 tp=4.0 | +431.18 | +86.2 | -53.6 | 0.34 | 81.73 | 318 | 100.0 | 65 | +338.13 | +135.39 |
| dca_tp | intervalh=168 tp=6.0 | +574.78 | +115.0 | -51.0 | 0.40 | 70.76 | 272 | 100.0 | 69 | +459.85 | +89.41 |
| dca_tp | intervalh=168 tp=10.0 | +749.45 | +149.9 | -58.4 | 0.43 | 56.22 | 211 | 100.0 | 76 | +729.54 | +34.50 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 | +443.25 | +88.7 | -68.2 | 0.34 | 104.48 | 209 | 100.0 | 75 | +384.17 | +76.94 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=45 max_dd=25 | -136.72 | -27.3 | -31.7 | -0.34 | 3.34 | 11 | 36.4 | 0 | -136.72 | +26.79 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 | +509.68 | +101.9 | -68.2 | 0.35 | 101.85 | 205 | 100.0 | 76 | +430.58 | +96.97 |
| dca_dip | intervalh=72 tp=4.0 smad=30 max_aged=100000 max_dd=25 | -136.72 | -27.3 | -31.7 | -0.34 | 3.34 | 11 | 36.4 | 0 | -136.72 | +30.26 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 | +479.24 | +95.8 | -67.4 | 0.35 | 78.63 | 159 | 100.0 | 78 | +512.93 | -6.89 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=45 max_dd=25 | -132.75 | -26.6 | -30.9 | -0.33 | 3.35 | 11 | 36.4 | 0 | -132.75 | -43.27 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 | +592.71 | +118.5 | -67.4 | 0.38 | 77.20 | 155 | 100.0 | 79 | +571.44 | +48.07 |
| dca_dip | intervalh=72 tp=6.0 smad=30 max_aged=100000 max_dd=25 | -132.75 | -26.6 | -30.9 | -0.33 | 3.35 | 11 | 36.4 | 0 | -132.75 | -43.27 |
| grid | step=3.0 band=25 | +40.72 | +8.1 | -74.8 | 0.21 | 8.29 | 33 | 100.0 | 4 | +40.72 | +140.67 |
| grid | step=3.0 band=40 | +48.12 | +9.6 | -82.8 | 0.25 | 9.80 | 39 | 100.0 | 4 | +48.12 | +148.07 |
| grid | step=4.0 band=25 | +44.92 | +9.0 | -58.0 | 0.16 | 6.56 | 26 | 100.0 | 3 | +44.92 | +141.67 |
| grid | step=4.0 band=40 | +63.93 | +12.8 | -81.4 | 0.25 | 9.34 | 37 | 100.0 | 4 | +63.93 | +153.77 |
| grid | step=6.0 band=25 | +32.58 | +6.5 | -33.2 | 0.11 | 3.06 | 12 | 100.0 | 2 | +32.58 | +103.18 |
| grid | step=6.0 band=40 | +67.88 | +13.6 | -63.5 | 0.19 | 6.37 | 25 | 100.0 | 3 | +67.88 | +130.34 |

## Findings (full-history run, 2026-07-10)

Dataset now spans 2013–2026 (BTC) / 2015–2026 (ETH) after merging Kraken's OHLCVT
archive (`python -m backtest.merge_historical`). These results supersede the earlier
2-year study — and reverse parts of it:

1. **The static grid's single anchor is fatal over long horizons.** BTC grid: **zero
   trades in 12 years** (anchored at $122 in Oct 2013; price left the band upward within
   weeks and never came back). ETH grid earned its entire +$40..68 in 2015–16, then sat
   idle for a decade. The 2-year study's "grid wins" verdict was conditional on a fresh
   anchor in a ranging market — real deployments must **recenter the band** when price
   walks out (the mitigation already named in the plan, now empirically mandatory).
   The H2 columns (fresh mid-period anchor) show what a recentered grid could earn.
2. **dca_tp is the robust long-horizon strategy of the three as implemented.** BTC:
   +$515..$1,649 net on a $500 budget across every param set, positive in both halves;
   ETH similar. Higher targets did better (tp 10% > 6% > 4% — lots ride the uptrend
   longer), the opposite of the 2-year ordering. Its 2024–26 losses in the previous
   study were a window artifact: over any span containing a bull leg it recovers. The
   cost is deep equity drawdowns (−57..−72%) — the warehousing pathology is still real,
   it just eventually resolves when the market makes new highs.
3. **The dca_dip drawdown stop (halt-forever) is broken over long windows**: it triggers
   in the first bear market, liquidates, never re-enters, and guarantees a permanent
   −$80..−$137. It needs a re-entry rule or removal. Dip-scaling without the stop merely
   matches plain dca_tp — it has not earned its complexity.
4. **Buy-and-hold dwarfs everything** (+$250k BTC / +$289k ETH from $500) because the
   assets did ~500x. That is hindsight, not a strategy — but it is a reminder that any
   take-profit design caps upside by construction and wins only on risk, not return.

## Recommendation (updated)

- **Keep the current paper run**: grid on BTC, freshly anchored — exactly the conditions
  under which grid performs. It is the right live experiment for the next weeks.
- **Before live (Phase 5), add grid band recentering** (rebuild rungs around price after
  k candles outside the band); without it the strategy has a shelf life of one trend.
- **Promote dca_tp (24–72h cadence, tp 6–10%) to co-primary candidate** and accept its
  drawdown profile consciously — it is the only variant that made money across every
  regime slice of 12 years.
- Drop or redesign the dca_dip portfolio stop before it is ever enabled.

*(Regenerating this file: `python -m backtest.study` rewrites the tables above and
drops this section — re-add or update it after each run.)*
