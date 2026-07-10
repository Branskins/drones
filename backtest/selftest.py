"""Deterministic engine self-test on synthetic candles (no network, no DB).

    python -m backtest.selftest

Exits non-zero on any assertion failure. Covers: limit fill rules,
no-lookahead, take-profit round trip with net fee math, budget cap, and the
grid buy->sell->re-arm cycle.
"""

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from backtest.engine import Engine
from bot.models import FeeModel, Intent, Portfolio
from bot.strategies import DcaTakeProfit, Grid, Strategy

FEES = FeeModel(maker_pct=0.25, taker_pct=0.40)
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candles(rows: list[tuple]) -> pd.DataFrame:
    """rows: (open, high, low, close)"""
    return pd.DataFrame([
        {'ts': T0 + timedelta(days=i), 'open': o, 'high': h, 'low': l,
         'close': c, 'volume': 1.0}
        for i, (o, h, l, c) in enumerate(rows)
    ])


class OneShotBuy(Strategy):
    """Places a single limit buy at a fixed price on the first candle."""
    name = 'oneshot'

    def __init__(self, params, fees=None):
        super().__init__(params, fees)
        self.placed = False

    def on_candle(self, candle, portfolio, broker):
        if self.placed:
            return []
        self.placed = True
        return [Intent(side='buy', ordertype='limit', volume=1.0,
                       price=self.params['limit'], reason='test', ttl=0)]

    def on_buy_fill(self, lot, candle):
        return []  # no take-profit; keep the lot


def check(name: str, cond: bool, detail: str = '') -> bool:
    print(f'{"OK  " if cond else "FAIL"} {name} {detail}')
    return cond


def main() -> int:
    ok = True

    # 1. Limit buy: no fill while low > limit; fills at limit when low touches.
    cs = candles([(100, 101, 99, 100), (100, 102, 96, 101), (101, 103, 94, 95)])
    e = Engine(cs, OneShotBuy({'limit': 95.0, 'budget_usd': 1000}, FEES),
               Portfolio(budget_usd=1000), FEES).run()
    ok &= check('limit buy waits above limit, fills at limit',
                len(e.fills) == 1 and e.fills[0].price == 95.0
                and e.fills[0].ts == cs.ts[2])

    # 2. No lookahead: crossable on the placement candle, must NOT fill there.
    cs = candles([(100, 101, 90, 100), (100, 101, 99, 100)])
    e = Engine(cs, OneShotBuy({'limit': 95.0, 'budget_usd': 1000}, FEES),
               Portfolio(budget_usd=1000), FEES).run()
    ok &= check('no lookahead on placement candle', len(e.fills) == 0)

    # 3. dca_tp round trip: entry limit at close(100) fills next day at 100,
    #    resting sell at net +4% target fills when high crosses it.
    target = (100.0 * (1 + 0.0025)) * 1.04 / (1 - 0.0025)  # cost+fee, net tp, exit fee
    cs = candles([(100, 100, 100, 100), (100, 100, 99, 100),
                  (100, 110, 100, 109), (109, 109, 108, 108)])
    p = Portfolio(budget_usd=100)
    strat = DcaTakeProfit({'budget_usd': 100, 'batch_usd': 50,
                           'interval_hours': 24 * 30, 'tp_pct': 4.0}, FEES)
    e = Engine(cs, strat, p, FEES).run()
    sells = [f for f in e.fills if f.side == 'sell']
    lot = p.lots[0]
    net_pct = lot.realized_usd / (lot.cost_usd + lot.fee_usd) * 100
    ok &= check('dca_tp sell price = net-of-fees target',
                len(sells) == 1 and abs(sells[0].price - target) < 0.01,
                f'(sell @{sells[0].price:.2f} vs {target:.2f})' if sells else '')
    ok &= check('dca_tp realized gain is net +4%',
                abs(net_pct - 4.0) < 0.01, f'(net {net_pct:.3f}%)')

    # 4. Budget cap: $100 budget, $50 batches, daily cadence, falling prices
    #    (every entry fills) -> exactly 2 lots ever open.
    cs = candles([(100 - i, 101 - i, 98 - i, 100 - i) for i in range(10)])
    p = Portfolio(budget_usd=100)
    strat = DcaTakeProfit({'budget_usd': 100, 'batch_usd': 50,
                           'interval_hours': 24, 'tp_pct': 50.0}, FEES)
    e = Engine(cs, strat, p, FEES).run()
    ok &= check('budget cap holds', len(p.lots) == 2 and p.cash_usd >= 0,
                f'(lots={len(p.lots)}, cash={p.cash_usd:.2f})')

    # 5. Grid cycle: anchor 100, step 5% -> rung at 95. Dip fills the rung,
    #    rally fills its sell one step up, dip fills the re-armed rung again.
    cs = candles([(100, 100, 100, 100),   # init: rungs placed
                  (100, 100, 94, 96),     # rung 95 fills -> sell rests at ~99.75
                  (96, 101, 96, 100),     # sell fills
                  (100, 100, 93, 94),     # re-armed rung 95 fills again
                  (94, 95, 93, 94)])
    p = Portfolio(budget_usd=100)
    strat = Grid({'budget_usd': 100, 'batch_usd': 50, 'step_pct': 5.0,
                  'band_pct': 10.0, 'min_net_pct': 0.5}, FEES)
    e = Engine(cs, strat, p, FEES).run()
    buys = [f for f in e.fills if f.side == 'buy']
    sells = [f for f in e.fills if f.side == 'sell']
    ok &= check('grid: buy -> sell -> re-armed buy',
                len(buys) == 2 and len(sells) == 1
                and abs(buys[0].price - 95.0) < 0.01
                and abs(buys[1].price - 95.0) < 0.01
                and sells[0].price > 95.0 * 1.049,
                f'(buys={[round(b.price, 2) for b in buys]}, '
                f'sells={[round(s.price, 2) for s in sells]})')
    ok &= check('grid round trip is net positive after fees',
                p.realized_cum_usd > 0, f'(realized={p.realized_cum_usd:.2f})')

    print('\nSELFTEST ' + ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
