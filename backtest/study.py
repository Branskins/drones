"""Strategy comparison study.

Runs S1/S2/S3 parameter sweeps over the cached daily candles for XBTUSD and
ETHUSD, on the full period and on each half (H1 / H2) as regime slices, and
writes docs/strategy-study.md.

    python -m backtest.study
"""

import itertools
import os

import pandas as pd

from backtest.engine import Engine
from backtest.metrics import buy_and_hold, compute_metrics
from bot.data import load_candles
from bot.models import FeeModel, Portfolio
from bot.strategies import REGISTRY

BUDGET = 500.0
BATCH = 50.0
FEES = FeeModel(maker_pct=0.25, taker_pct=0.40)

SWEEPS = {
    'dca_tp': [
        {'interval_hours': ih, 'tp_pct': tp}
        for ih, tp in itertools.product([24, 72, 168], [2.0, 4.0, 6.0, 10.0])
    ],
    'dca_dip': [
        {'interval_hours': 72, 'tp_pct': tp, 'sma_days': 30,
         'max_age_days': age, 'max_dd_pct': dd}
        for tp, age, dd in itertools.product(
            [4.0, 6.0], [45, 100000], [None, 25])
    ],
    'grid': [
        {'step_pct': step, 'band_pct': band}
        for step, band in itertools.product([3.0, 4.0, 6.0], [25, 40])
    ],
}


def run_one(name: str, params: dict, candles: pd.DataFrame) -> dict:
    full_params = {'budget_usd': BUDGET, 'batch_usd': BATCH, **params}
    strategy = REGISTRY[name](full_params, FEES)
    portfolio = Portfolio(budget_usd=BUDGET)
    engine = Engine(candles, strategy, portfolio, FEES).run()
    return compute_metrics(engine, BUDGET)


def param_label(params: dict) -> str:
    return ' '.join(f'{k.replace("_pct", "").replace("_hours", "h").replace("_days", "d")}={v}'
                    for k, v in params.items() if v is not None)


def main():
    slices = {}
    for pair in ['XBTUSD', 'ETHUSD']:
        df = load_candles(pair, 1440)
        mid = len(df) // 2
        slices[pair] = {
            'FULL': df,
            'H1': df.iloc[:mid].reset_index(drop=True),
            'H2': df.iloc[mid:].reset_index(drop=True),
        }

    lines = ['# Strategy study — backtest results', '']
    lines.append(f'Budget ${BUDGET:.0f}, batch ${BATCH:.0f}, maker {FEES.maker_pct}% / '
                 f'taker {FEES.taker_pct}%, conservative fills (see backtest/engine.py).')
    lines.append('Data: Kraken daily candles (public OHLC, 720 candles/pair — ~2 years). '
                 'H1/H2 = first/second half of the period as regime slices.')
    lines.append('')

    all_rows = []
    for pair, pair_slices in slices.items():
        full = pair_slices['FULL']
        lines.append(f'## {pair}')
        lines.append('')
        lines.append(f"Period: {full.ts.min():%Y-%m-%d} .. {full.ts.max():%Y-%m-%d}. "
                     f"Price {full.close.iloc[0]:,.0f} -> {full.close.iloc[-1]:,.0f} "
                     f"({(full.close.iloc[-1]/full.close.iloc[0]-1)*100:+.1f}%).")
        bh = buy_and_hold(full, BUDGET, FEES)
        lines.append(f"Buy-and-hold benchmark: net ${bh['net_pnl']:+,.2f} "
                     f"({bh['return_pct']:+.1f}%), maxDD {bh['max_drawdown_pct']:.1f}%.")
        lines.append('')
        header = ('| strategy | params | net$ FULL | ret% | maxDD% | sharpe | fees$ | '
                  'trips | win% | util% | net$ H1 | net$ H2 |')
        lines.append(header)
        lines.append('|' + '---|' * 12)

        for name, param_sets in SWEEPS.items():
            for params in param_sets:
                m_full = run_one(name, params, pair_slices['FULL'])
                m_h1 = run_one(name, params, pair_slices['H1'])
                m_h2 = run_one(name, params, pair_slices['H2'])
                row = {
                    'pair': pair, 'strategy': name, 'params': param_label(params),
                    **{f'{k}': v for k, v in m_full.items()},
                    'h1_net': m_h1['net_pnl'], 'h2_net': m_h2['net_pnl'],
                }
                all_rows.append(row)
                lines.append(
                    f"| {name} | {param_label(params)} | {m_full['net_pnl']:+.2f} "
                    f"| {m_full['return_pct']:+.1f} | {m_full['max_drawdown_pct']:.1f} "
                    f"| {m_full['sharpe']:.2f} | {m_full['fees_usd']:.2f} "
                    f"| {m_full['round_trips']} | {m_full['win_rate_pct'] or '-'} "
                    f"| {m_full['utilization_pct']:.0f} "
                    f"| {m_h1['net_pnl']:+.2f} | {m_h2['net_pnl']:+.2f} |")
                print(f"{pair} {name:8s} {param_label(params):48s} "
                      f"net={m_full['net_pnl']:+8.2f} dd={m_full['max_drawdown_pct']:6.1f} "
                      f"h1={m_h1['net_pnl']:+8.2f} h2={m_h2['net_pnl']:+8.2f}")
        lines.append('')

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', 'strategy-study.md')
    results = pd.DataFrame(all_rows)
    csv_out = out.replace('.md', '.csv')
    results.to_csv(csv_out, index=False)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'\nwrote {out} and {csv_out}')


if __name__ == '__main__':
    main()
