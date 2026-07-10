"""Phase 6 groundwork: import the pre-bot 'available' buy lots from `trades`
into `lots` (strategy='legacy', mode='live') with their +1% net-gain targets.

This script places NO orders — it only computes and stores targets, then
prints the rolling-window report (which lots would get resting sells first).
Actually placing the resting limit sells is live trading and stays behind the
live gate (ALLOW_LIVE=1 + confirm_live), per docs/human-actions.md.

    python -m bot.legacy_import
"""

from bot import db, ticker

EXIT_FEE_PCT = 0.25   # maker, post-only
NET_GAIN_PCT = 1.0    # decided 2026-07-09
ASSET_PAIR = {'XXBT': 'XBTUSD', 'XETH': 'ETHUSD'}


def target_price(cost_usd: float, fee_usd: float, volume: float) -> float:
    return (cost_usd + fee_usd) * (1 + NET_GAIN_PCT / 100) / (
        volume * (1 - EXIT_FEE_PCT / 100))


def main():
    sb = db.client()
    trades = (sb.table('trades').select('*')
              .eq('side', 'buy').eq('status', 'available').execute().data)
    existing = {r['base_ledger_id']
                for r in sb.table('lots').select('base_ledger_id')
                .eq('strategy', 'legacy').execute().data}

    imported = 0
    for t in trades:
        if t['base_ledger_id'] in existing:
            continue
        tp = target_price(float(t['cost_usd']), float(t['fee_usd']),
                          float(t['volume']))
        db.insert_lot(
            sb, mode='live', strategy='legacy', asset=t['asset'],
            volume=float(t['volume']), cost_usd=float(t['cost_usd']),
            fee_usd=float(t['fee_usd']), buy_order_id=None,
            target_price=round(tp, 2), opened_at=t['executed_at'],
            base_ledger_id=t['base_ledger_id'])
        imported += 1
    print(f'imported {imported} legacy lots ({len(existing)} already present)')

    # Rolling-window report: which lots are nearest their targets.
    config = db.load_config(sb)
    window = config.get('legacy_exit_window') or {}
    max_resting = int(window.get('max_resting_orders', 20))
    max_distance = float(window.get('max_distance_pct', 15))

    lots = db.lots(sb, 'live', 'legacy', states=['open', 'exiting'])
    prices = {a: ticker.fetch(p)['last'] for a, p in ASSET_PAIR.items()}
    ranked = sorted(
        ({'lot': l,
          'distance_pct': (float(l['target_price']) / prices[l['asset']] - 1) * 100}
         for l in lots),
        key=lambda x: x['distance_pct'])

    print(f'\nRolling window (max {max_resting} resting sells, '
          f'targets within {max_distance}% of market):')
    eligible = 0
    for item in ranked[:max_resting]:
        l, d = item['lot'], item['distance_pct']
        mark = 'PLACE' if d <= max_distance else 'wait '
        if d <= max_distance:
            eligible += 1
        print(f"  {mark} {l['asset']} vol={float(l['volume']):.8f} "
              f"target={float(l['target_price']):>10.2f} (+{d:.1f}% from market)")
    print(f'\n{eligible} lot(s) currently inside the placement window. '
          'No orders were placed (live gate).')


if __name__ == '__main__':
    main()
