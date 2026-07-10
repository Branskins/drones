"""Validation gate: drive the shared Portfolio accounting with the REAL
baseline fills (from Supabase) and require it to reproduce every realized_pnl
row within a cent. If this fails, no backtest result can be trusted.

    python -m backtest.validate_baseline
"""

import os
import sys
from datetime import datetime, timezone

import dotenv
import pandas as pd
from supabase import create_client

from bot.models import Portfolio


def main() -> int:
    dotenv.load_dotenv()
    sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

    trades = pd.DataFrame(sb.table('trades').select('*').execute().data)
    hist = pd.DataFrame(sb.table('trades_history').select('*').execute().data)
    pnl = pd.DataFrame(sb.table('realized_pnl').select('*').execute().data)

    sold = trades[(trades['side'] == 'buy') & (trades['status'] == 'sold')]
    fills = hist.groupby('order_txid').agg(
        proceeds=('cost', 'sum'), fee=('fee', 'sum'), time=('time', 'min'))

    portfolio = Portfolio(budget_usd=0, cash_usd=10_000)
    failures = 0
    checked = 0

    for row in sold.itertuples():
        if row.order_txid not in fills.index:
            continue  # sold in DB but sell fill not yet in trades_history
        fill = fills.loc[row.order_txid]
        lot = portfolio.open_lot(
            strategy='baseline', volume=row.volume, cost_usd=row.cost_usd,
            fee_usd=row.fee_usd,
            ts=datetime.fromisoformat(row.executed_at).replace(tzinfo=timezone.utc))
        portfolio.close_lot(
            lot, proceeds_usd=float(fill.proceeds), exit_fee_usd=float(fill.fee),
            ts=datetime.fromtimestamp(float(fill.time), tz=timezone.utc))

        expected = pnl[pnl['buy_base_ledger_id'] == row.base_ledger_id]
        if expected.empty:
            print(f'MISSING realized_pnl row for {row.base_ledger_id}')
            failures += 1
            continue
        expected_gain = float(expected['gain_loss_usd'].iloc[0])
        got = lot.realized_usd
        ok = abs(got - expected_gain) < 0.01
        checked += 1
        status = 'OK  ' if ok else 'FAIL'
        print(f'{status} {row.base_ledger_id} ({row.asset}): '
              f'portfolio={got:+.4f} realized_pnl={expected_gain:+.4f}')
        if not ok:
            failures += 1

    total_expected = float(pnl['gain_loss_usd'].sum())
    print(f'\nchecked={checked} lots | portfolio realized={portfolio.realized_cum_usd:+.4f} '
          f'| realized_pnl total={total_expected:+.4f}')
    if failures or checked == 0:
        print('VALIDATION FAILED')
        return 1
    print('VALIDATION PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
