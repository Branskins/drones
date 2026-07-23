"""Import the pre-bot 'available' buy lots from `trades` into `lots`
(strategy='legacy', mode='live') with their net-gain exit targets, and
recompute those targets when the fee/gain assumptions change.

Targets are derived from strategy_config, NOT hardcoded:
  - `fee_maker_pct`        exit fee assumed when solving for the target
  - `legacy_min_gain_pct`  required net gain after that fee

    python -m bot.legacy_import                     # import new lots
    python -m bot.legacy_import --recompute-targets # refresh existing targets

Neither mode places orders. `--recompute-targets` may CANCEL resting sells
that are priced below the corrected target (they would sell too cheap); the
next live cycle re-places them via bot/legacy.py.
"""

import argparse

from bot import db, executor, ticker

ASSET_PAIR = {'XXBT': 'XBTUSD', 'XETH': 'ETHUSD'}


def exit_params(config: dict) -> tuple[float, float]:
    """(exit_fee_pct, net_gain_pct) — the assumptions behind every target."""
    return (float(config.get('fee_maker_pct', 0.25)),
            float(config.get('legacy_min_gain_pct', 1.0)))


def target_price(cost_usd: float, fee_usd: float, volume: float,
                 exit_fee_pct: float, gain_pct: float) -> float:
    """Price at which selling nets `gain_pct` over (cost + entry fee)."""
    return ((cost_usd + fee_usd) * (1 + gain_pct / 100)
            / (volume * (1 - exit_fee_pct / 100)))


def import_lots(sb, config: dict) -> int:
    exit_fee, gain = exit_params(config)
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
                          float(t['volume']), exit_fee, gain)
        db.insert_lot(
            sb, mode='live', strategy='legacy', asset=t['asset'],
            volume=float(t['volume']), cost_usd=float(t['cost_usd']),
            fee_usd=float(t['fee_usd']), buy_order_id=None,
            target_price=round(tp, 2), opened_at=t['executed_at'],
            base_ledger_id=t['base_ledger_id'])
        imported += 1
    print(f'imported {imported} legacy lots ({len(existing)} already present) '
          f'[exit_fee={exit_fee}% gain={gain}%]')
    return imported


def recompute_targets(sb, config: dict) -> None:
    """Refresh stored targets after a fee/gain change, and drop resting sells
    that would now sell too cheap."""
    exit_fee, gain = exit_params(config)
    lots = db.lots(sb, 'live', 'legacy', states=['open', 'exiting'])
    print(f'recomputing {len(lots)} open legacy targets '
          f'[exit_fee={exit_fee}% gain={gain}%]')

    changed = 0
    new_targets: dict[int, float] = {}
    for lot in lots:
        new = round(target_price(float(lot['cost_usd']), float(lot['fee_usd']),
                                 float(lot['volume']), exit_fee, gain), 2)
        new_targets[lot['id']] = new
        old = float(lot['target_price']) if lot['target_price'] else None
        if old is None or abs(new - old) >= 0.01:
            db.update_lot(sb, lot['id'], {'target_price': new})
            changed += 1
    print(f'  updated {changed} target(s)')

    # A resting sell is stale only if it is BELOW the corrected target —
    # one placed above it (at market ask) is already better than required.
    broker = executor.DbBroker(sb, 'live', 'legacy')
    stale = [o for o in broker.open_orders()
             if o.side == 'sell' and o.lot_id in new_targets
             and o.price is not None
             and o.price < new_targets[o.lot_id] - 0.01]
    print(f'  {len(stale)} resting sell(s) priced below the new target')
    for o in stale:
        broker.cancel(o.id)
        print(f'    canceled order #{o.id} @{o.price:,.2f} '
              f'(new target {new_targets[o.lot_id]:,.2f})')
        db.log_event(sb, 'info', 'legacy_target_recomputed',
                     {'lot_id': o.lot_id, 'old_price': o.price,
                      'new_target': new_targets[o.lot_id]})


def window_report(sb, config: dict) -> None:
    window = config.get('legacy_exit_window') or {}
    max_resting = int(window.get('max_resting_orders', 20))
    max_distance = float(window.get('max_distance_pct', 15))
    lots = [l for l in db.lots(sb, 'live', 'legacy', states=['open', 'exiting'])
            if l.get('target_price')]
    if not lots:
        print('\nno open legacy lots')
        return
    prices = {a: ticker.fetch(p)['last'] for a, p in ASSET_PAIR.items()
              if any(l['asset'] == a for l in lots)}
    ranked = sorted(({'lot': l,
                      'd': (float(l['target_price']) / prices[l['asset']] - 1) * 100}
                     for l in lots), key=lambda x: x['d'])
    print(f'\nRolling window (max {max_resting} resting sells, within {max_distance}%):')
    eligible = 0
    for item in ranked[:max_resting]:
        l, d = item['lot'], item['d']
        mark = 'PLACE' if d <= max_distance else 'wait '
        eligible += d <= max_distance
        print(f"  {mark} {l['asset']} vol={float(l['volume']):.8f} "
              f"target={float(l['target_price']):>10.2f} ({d:+.1f}% from market)")
    print(f'\n{eligible} lot(s) inside the placement window. No orders placed here.')


def backfill_trades(sb) -> None:
    """One-time reconcile: for every already-closed legacy lot, flip its pre-bot
    `trades` buy row to 'sold' with the sell's order_txid. Idempotent — lots
    whose trades row is already sold are skipped. New closures are handled live
    in bot/executor.py:_apply_fill; this catches lots closed before that wiring."""
    closed = [l for l in db.lots(sb, 'live', 'legacy', states=['closed'])
              if l.get('base_ledger_id')]
    flipped = 0
    for lot in closed:
        if not lot.get('sell_order_id'):
            print(f"  lot {lot['id']}: no sell_order_id, skipped")
            continue
        order = (sb.table('orders').select('kraken_txid')
                 .eq('id', lot['sell_order_id']).execute().data)
        txid = order[0]['kraken_txid'] if order else None
        if not txid:
            print(f"  lot {lot['id']}: sell order has no kraken_txid, skipped")
            continue
        n = db.mark_trade_sold(sb, lot['base_ledger_id'], txid)
        if n:
            flipped += 1
            print(f"  lot {lot['id']} ({lot['base_ledger_id']}) -> trades sold, "
                  f"order_txid={txid}")
    print(f'backfilled {flipped} trades row(s); '
          f'{len(closed)} closed legacy lot(s) checked')
    print('run `python pipeline.py` (or sync_realized_pnl) to populate realized_pnl')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recompute-targets', action='store_true',
                        help='refresh targets of existing lots from current config')
    parser.add_argument('--backfill-trades', action='store_true',
                        help='flip closed legacy lots to sold in the old trades table')
    args = parser.parse_args()

    sb = db.client()
    config = db.load_config(sb)
    if args.backfill_trades:
        backfill_trades(sb)
        return
    if args.recompute_targets:
        recompute_targets(sb, config)
    else:
        import_lots(sb, config)
    window_report(sb, config)


if __name__ == '__main__':
    main()
