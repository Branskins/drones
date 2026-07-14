"""The bot's stateless cycle — run by GitHub Actions cron (or manually):

    python -m bot.run

Each run: refresh data -> reconcile fills -> guardrails -> strategy decision
-> execute -> snapshot. Mode comes from strategy_config ('off' | 'paper' |
'live'); paper mode never touches Kraken's private API.

Live mode: reconciliation (read-only private calls) always runs, but new
orders are only created while the double gate is open (env ALLOW_LIVE=1 AND
config confirm_live=true), and AddOrder carries validate=true until
live_validate_only is set false. Legacy lot exits (bot/legacy.py) activate
with the same gate.
"""

import sys
import traceback
from datetime import datetime, timedelta, timezone

from bot import data, db, executor, legacy, monitor, risk, ticker
from bot.models import Candle, FeeModel, Lot
from bot.strategies import REGISTRY


def hydrate_strategy(sb, strategy, *, mode: str, candles, config: dict) -> None:
    name = strategy.name
    rows = (sb.table('orders').select('created_at')
            .eq('mode', mode).eq('strategy', name).eq('side', 'buy')
            .neq('state', 'failed')
            .order('created_at', desc=True).limit(1).execute().data)
    state: dict = {}
    if rows:
        state['last_entry_ts'] = datetime.fromisoformat(rows[0]['created_at'])
    sma_days = int(config.get('sma_days', 30))
    state['closes'] = list(candles['close'].tail(sma_days))
    any_orders = (sb.table('orders').select('id').eq('mode', mode)
                  .eq('strategy', name).limit(1).execute().data)
    state['initialized'] = bool(any_orders)
    state['peak_equity'] = risk.peak_equity(sb, mode)
    strategy.hydrate(**state)


def cancel_stale_entries(sb, broker, config: dict) -> None:
    """Entry limit buys that sat unfilled for 2x the cadence get re-priced by
    the next decision instead of chasing forever. Grid rungs (GTC) are exempt —
    grid has no interval_hours param."""
    interval_h = config.get('interval_hours')
    if not interval_h:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2 * float(interval_h))
    for order in broker.open_orders():
        placed = datetime.fromisoformat(order.created_at)
        if order.side == 'buy' and order.lot_id is None and placed < cutoff:
            broker.cancel(order.id)
            db.log_event(sb, 'info', 'stale_entry_canceled',
                         {'order_id': order.id, 'price': order.price})


def process_fills(sb, fills, strategy, candle, *, mode: str, name: str,
                  pair: str, config: dict) -> None:
    """Run the strategy's fill hooks (rest the paired sell / re-arm rungs)."""
    for fill in fills:
        db.log_event(sb, 'info', f'{mode}_fill', {
            'side': fill['order']['side'], 'price': fill['price'],
            'volume': float(fill['order']['volume']),
            'reason': fill['order'].get('reason')})
        side = fill['order']['side']
        follow_ups = []
        if side == 'buy' and fill['lot'] is not None:
            portfolio = executor.load_portfolio(
                sb, mode, name, float(config.get('budget_usd', 500)))
            lot = next((l for l in portfolio.lots
                        if l.id == fill['lot']['id']), None)
            if lot is not None:
                follow_ups = strategy.on_buy_fill(lot, candle) or []
        elif side == 'sell' and fill['lot'] is not None:
            row = sb.table('lots').select('*').eq('id', fill['lot']['id']) \
                .execute().data[0]
            lot_obj = Lot(id=row['id'], strategy=name,
                          volume=float(row['volume']),
                          cost_usd=float(row['cost_usd']),
                          fee_usd=float(row['fee_usd']),
                          opened_at=datetime.fromisoformat(row['opened_at']),
                          state='closed')
            follow_ups = strategy.on_sell_fill(lot_obj, candle) or []
        executor.execute_intents(sb, follow_ups, mode=mode, strategy=name,
                                 pair=pair, config=config)


def cycle() -> int:
    sb = db.client()
    config = db.load_config(sb)
    mode = config.get('mode', 'off')
    if mode == 'off':
        print('mode=off, nothing to do')
        return 0
    if config.get('kill_switch') is True:
        db.log_event(sb, 'warn', 'kill_switch_active', {'mode': mode})
        return 0

    pair = config.get('pair', 'XBTUSD')
    name = config.get('active_strategy', 'dca_tp')
    fees = FeeModel(maker_pct=float(config.get('fee_maker_pct', 0.25)),
                    taker_pct=float(config.get('fee_taker_pct', 0.40)))
    params = {
        'budget_usd': float(config.get('budget_usd', 500)),
        'batch_usd': float(config.get('batch_usd', 50)),
        **(config.get(name) or {}),
    }
    strategy = REGISTRY[name](params, fees)

    # 1. Market data: refresh candle cache (guardrail checks freshness).
    try:
        candles = data.refresh_cache(pair, 1440)
        data.upsert_market_data(
            sb, pair, 1440, candles,
            since=datetime.now(timezone.utc) - timedelta(days=5))
    except Exception as exc:  # noqa: BLE001
        db.log_event(sb, 'error', 'candle_refresh_failed', {'error': str(exc)[:300]})
        candles = data.load_candles(pair, 1440)

    tick = ticker.fetch(pair)
    now = datetime.now(timezone.utc)
    decision_candle = Candle(ts=now, open=tick['last'], high=tick['last'],
                             low=tick['last'], close=tick['last'], volume=0.0)

    hydrate_strategy(sb, strategy, mode=mode, candles=candles, config=params)

    # 2. Reconcile fills from the previous cycle, then run fill hooks.
    if mode == 'paper':
        fills = executor.reconcile_paper(sb, strategy=name, pair=pair,
                                         ticker=tick, fees=fees)
    else:
        fills = executor.reconcile_live(sb, strategy=name, pair=pair)
        for legacy_pair in ('XBTUSD', 'ETHUSD'):
            for fill in executor.reconcile_live(sb, strategy='legacy',
                                                pair=legacy_pair):
                db.log_event(sb, 'info', 'legacy_exit_filled', {
                    'lot_id': (fill['lot'] or {}).get('id'),
                    'price': fill['price'],
                    'volume': float(fill['order']['volume'])})
    process_fills(sb, fills, strategy, decision_candle,
                  mode=mode, name=name, pair=pair, config=config)

    # 3. Decide.
    broker = executor.DbBroker(sb, mode, name)
    cancel_stale_entries(sb, broker, params)
    portfolio = executor.load_portfolio(sb, mode, name, params['budget_usd'])
    gate_open = mode == 'paper' or executor.live_gate_open(config)
    if not gate_open:
        db.log_event(sb, 'warn', 'live_gate_closed_skip_execution',
                     {'note': 'reconcile + snapshot only; see docs/human-actions.md item 7'})
        intents = []
    elif not risk.data_fresh(candles):
        db.log_event(sb, 'error', 'stale_market_data',
                     {'latest': str(candles["ts"].iloc[-1])})
        intents = []
    else:
        intents = strategy.on_candle(decision_candle, portfolio, broker)

    # Persist any target changes the strategy made to existing lots (recycling).
    for intent in intents:
        if intent.side == 'sell' and intent.lot_id is not None:
            db.update_lot(sb, intent.lot_id, {'target_price': intent.price})

    equity = portfolio.equity(tick['last'])
    allowed = risk.filter_intents(sb, intents, mode=mode, config=config,
                                  portfolio=portfolio, broker=broker,
                                  equity=equity)
    executor.execute_intents(sb, allowed, mode=mode, strategy=name, pair=pair,
                             config=config)

    # 3b. Legacy lot exits (live only; self-guards on gate + validate-only).
    if mode == 'live':
        legacy.manage(sb, config)

    # 4. Snapshot + alerting.
    monitor.snapshot_and_alert(sb, mode=mode, strategy=name, pair=pair,
                               tick=tick, config=config)
    print(f'cycle done: mode={mode} strategy={name} equity={equity:.2f} '
          f'open_lots={len(portfolio.open_lots())} intents={len(intents)} '
          f'executed={len(allowed)}')
    return 0


def main() -> int:
    try:
        return cycle()
    except Exception:
        traceback.print_exc()
        try:
            sb = db.client()
            db.log_event(sb, 'error', 'cycle_crashed',
                         {'trace': traceback.format_exc()[-800:]})
        except Exception:
            pass
        return 1


def cli() -> None:
    sys.exit(main())


if __name__ == '__main__':
    cli()
