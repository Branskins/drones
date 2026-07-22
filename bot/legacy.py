"""Phase 6: rolling-window resting sells for the legacy lots.

Keeps GTC limit sells resting for the legacy lots *nearest* their +1% net
targets, bounded by `legacy_exit_window` in strategy_config:

    {"max_resting_orders": 20, "max_distance_pct": 15}

so the account's open-order cap is never exhausted (78 lots + grid rungs
would not fit). Lots that drift outside the window get their resting sell
canceled to free the slot; lots that drift inside get one placed.

Only active when the live gate is open AND live_validate_only is false —
these are real GTC sell orders, so the validate-only smoke phase skips them
(a validate-canceled order would just be re-placed every cycle).
"""

from bot import db, executor, ticker
from bot.models import Intent
from bot.ticker import PAIR_ASSET

ASSET_PAIR = {asset: pair for pair, asset in PAIR_ASSET.items()}


def manage(sb, config: dict) -> None:
    if not executor.live_gate_open(config):
        return
    if config.get('live_validate_only', True):
        db.log_event(sb, 'info', 'legacy_skipped_validate_only', None)
        return

    window = config.get('legacy_exit_window') or {}
    max_resting = int(window.get('max_resting_orders', 20))
    max_distance = float(window.get('max_distance_pct', 15))

    lots = [l for l in db.lots(sb, 'live', 'legacy', states=['open', 'exiting'])
            if l.get('target_price')]
    if not lots:
        return

    prices = {asset: ticker.fetch(pair)['ask']
              for asset, pair in ASSET_PAIR.items()
              if any(l['asset'] == asset for l in lots)}

    broker = executor.DbBroker(sb, 'live', 'legacy')
    resting = {o.lot_id: o for o in broker.open_orders() if o.side == 'sell'}

    ranked = sorted(lots, key=lambda l: float(l['target_price'])
                    / prices[l['asset']])
    in_window = [
        l for l in ranked[:max_resting]
        if (float(l['target_price']) / prices[l['asset']] - 1) * 100 <= max_distance
    ]
    in_window_ids = {l['id'] for l in in_window}

    # Free slots: cancel resting sells for lots that left the window.
    for lot_id, order in list(resting.items()):
        if lot_id not in in_window_ids:
            broker.cancel(order.id)
            db.log_event(sb, 'info', 'legacy_sell_window_exit',
                         {'lot_id': lot_id, 'order_id': order.id})
            del resting[lot_id]

    # Self-correct stale prices: if a lot's target was raised (e.g. the fee
    # assumption changed), a sell resting BELOW it would now sell too cheap.
    # Cancel it; the placement loop below re-rests it at the correct price.
    # A sell above its target is already better than required — leave it.
    targets = {l['id']: float(l['target_price']) for l in lots}
    for lot_id, order in list(resting.items()):
        target = targets.get(lot_id)
        if target is not None and order.price is not None \
                and order.price < target - 0.01:
            broker.cancel(order.id)
            db.log_event(sb, 'info', 'legacy_sell_reprice',
                         {'lot_id': lot_id, 'old_price': order.price,
                          'new_target': target})
            del resting[lot_id]

    # Fill slots: place resting sells for window lots that lack one.
    for lot in in_window:
        if lot['id'] in resting:
            continue
        asset = lot['asset']
        # Never below target; if the market already trades above it, sell at
        # the ask instead (better than target, and post-only still rests).
        price = max(float(lot['target_price']), prices[asset])
        intent = Intent(side='sell', ordertype='limit',
                        volume=float(lot['volume']),
                        price=round(price, executor.PAIR_PRICE_DECIMALS[ASSET_PAIR[asset]]),
                        lot_id=lot['id'], reason='legacy:+1%net', ttl=0)
        executor.execute_intents(sb, [intent], mode='live', strategy='legacy',
                                 pair=ASSET_PAIR[asset], config=config)
        db.log_event(sb, 'info', 'legacy_sell_placed',
                     {'lot_id': lot['id'], 'asset': asset,
                      'price': intent.price, 'volume': intent.volume})
