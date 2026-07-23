"""Order execution + reconciliation.

Paper mode: orders are recorded in the `orders` table and filled against the
live public ticker by `reconcile_paper` on the next cycle — no private Kraken
call is ever made.

Live mode: `submit_live` places real orders via AddOrder and `reconcile_live`
tracks them via QueryOrders (with userref-based crash recovery). Submission is
double-gated: config `confirm_live` must be true AND the env var ALLOW_LIVE=1
must be set (the GitHub Actions workflow does not set it; a human enables it
deliberately). While `live_validate_only` is true, AddOrder is sent with
validate=true and executes nothing.

Both modes converge on `_apply_fill`, so paper and live fills hit the same
accounting path.
"""

import json
import os
from datetime import datetime, timezone

from bot import db
from bot.models import FeeModel, Intent, Lot
from bot.ticker import PAIR_ASSET

PAIR_PRICE_DECIMALS = {'XBTUSD': 1, 'ETHUSD': 2}


def live_gate_open(config: dict) -> bool:
    return (os.environ.get('ALLOW_LIVE') == '1'
            and config.get('confirm_live') is True)


class DbBroker:
    """Broker view over the orders table, matching the backtest Broker API."""

    class _Order:
        def __init__(self, row: dict):
            self.id = row['id']
            self.side = row['side']
            self.ordertype = row['ordertype']
            self.price = float(row['price']) if row['price'] is not None else None
            self.volume = float(row['volume'])
            self.lot_id = row['lot_id']
            self.reason = row.get('reason') or ''
            self.created_at = row['created_at']

    def __init__(self, sb, mode: str, strategy: str):
        self.sb = sb
        self.mode = mode
        self.strategy = strategy
        self._rows = db.open_orders(sb, mode, strategy)

    def open_orders(self) -> list['DbBroker._Order']:
        return [self._Order(r) for r in self._rows]

    def cancel(self, order_id: int) -> None:
        row = next((r for r in self._rows if r['id'] == order_id), None)
        if row is None:
            return
        if self.mode == 'live' and row.get('kraken_txid'):
            from bot import kraken_api
            try:
                kraken_api.cancel_order(row['kraken_txid'])
            except Exception as exc:  # noqa: BLE001
                # The order is still alive on Kraken — do NOT mark it canceled.
                db.log_event(self.sb, 'error', 'cancel_failed',
                             {'order_id': order_id,
                              'txid': row['kraken_txid'],
                              'error': str(exc)[:300]})
                return
        db.update_order(self.sb, order_id, {'state': 'canceled'})
        if row['side'] == 'sell' and row.get('lot_id'):
            db.update_lot(self.sb, row['lot_id'], {'state': 'open'})
        self._rows = [r for r in self._rows if r['id'] != order_id]

    def reserved_buy_usd(self) -> float:
        return sum(float(r['volume']) * float(r['price'])
                   for r in self._rows
                   if r['side'] == 'buy' and r['price'] is not None)


def load_portfolio(sb, mode: str, strategy: str, budget_usd: float):
    """Rebuild a bot.models-compatible portfolio view from the lots table."""
    rows = db.lots(sb, mode, strategy)
    lots = []
    realized = 0.0
    fees = 0.0
    deployed = 0.0
    for r in rows:
        lot = Lot(
            id=r['id'], strategy=strategy, volume=float(r['volume']),
            cost_usd=float(r['cost_usd']), fee_usd=float(r['fee_usd']),
            opened_at=datetime.fromisoformat(r['opened_at']),
            target_price=float(r['target_price']) if r['target_price'] else None,
            state=r['state'],
        )
        fees += lot.fee_usd
        if r['state'] == 'closed':
            proceeds = float(r['proceeds_usd'] or 0)
            realized += proceeds - lot.cost_usd - lot.fee_usd
        else:
            deployed += lot.cost_usd + lot.fee_usd
            lots.append(lot)

    from bot.models import Portfolio
    p = Portfolio(budget_usd=budget_usd,
                  cash_usd=budget_usd - deployed + realized)
    p.lots = lots
    p.realized_cum_usd = realized
    p.fees_cum_usd = fees
    return p


def execute_intents(sb, intents: list[Intent], *, mode: str, strategy: str,
                    pair: str, config: dict) -> list[dict]:
    """Persist intents as orders. Paper: mark open (resting on the paper book).
    Live: submit to Kraken."""
    created = []
    for intent in intents:
        row = db.insert_order(
            sb, mode=mode, strategy=strategy, pair=pair, side=intent.side,
            ordertype=intent.ordertype, price=intent.price,
            volume=intent.volume, lot_id=intent.lot_id, reason=intent.reason)
        if intent.lot_id is not None and intent.side == 'sell':
            db.update_lot(sb, intent.lot_id,
                          {'state': 'exiting', 'target_price': intent.price})
        if mode == 'paper':
            db.update_order(sb, row['id'], {'state': 'open'})
        else:
            submit_live(sb, row, config)
        created.append(row)
    return created


def _apply_fill(sb, row: dict, *, mode: str, volume: float, price: float,
                cost: float, fee: float) -> dict:
    """Record a fill: mark the order filled, then open or close the lot.
    Shared by paper and live reconciliation."""
    now = datetime.now(timezone.utc).isoformat()
    db.update_order(sb, row['id'], {
        'state': 'filled', 'filled_volume': volume,
        'avg_fill_price': price, 'fee_usd': round(fee, 6)})

    lot_row = None
    if row['side'] == 'buy':
        lot_row = db.insert_lot(
            sb, mode=mode, strategy=row['strategy'], asset=PAIR_ASSET[row['pair']],
            volume=volume, cost_usd=round(cost, 6),
            fee_usd=round(fee, 6), buy_order_id=row['id'],
            target_price=None, opened_at=now)
    elif row.get('lot_id'):
        db.update_lot(sb, row['lot_id'], {
            'state': 'closed', 'closed_at': now,
            'proceeds_usd': round(cost - fee, 6),
            'sell_order_id': row['id']})
        lot_row = {'id': row['lot_id']}
        # Bridge to the old pipeline accounting: a legacy lot maps 1:1 to a
        # pre-bot `trades` buy via base_ledger_id. Flip that row to 'sold' so
        # realized_pnl reflects the exit. Grid lots have no base_ledger_id and
        # are skipped inside mark_trade_sold.
        lot = (sb.table('lots').select('base_ledger_id')
               .eq('id', row['lot_id']).execute().data)
        base_ledger_id = lot[0]['base_ledger_id'] if lot else None
        if base_ledger_id and row.get('kraken_txid'):
            db.mark_trade_sold(sb, base_ledger_id, row['kraken_txid'])
    return {'order': row, 'lot': lot_row, 'price': price, 'fee': fee}


def reconcile_paper(sb, *, strategy: str, pair: str, ticker: dict,
                    fees: FeeModel) -> list[dict]:
    """Fill resting paper orders against the live ticker."""
    fills = []
    for row in db.open_orders(sb, 'paper', strategy):
        if row['pair'] != pair:
            continue
        price = None
        ordertype = row['ordertype']
        limit = float(row['price']) if row['price'] is not None else None
        if ordertype == 'market':
            price = ticker['ask'] if row['side'] == 'buy' else ticker['bid']
        elif row['side'] == 'buy' and ticker['ask'] <= limit:
            price = limit
        elif row['side'] == 'sell' and ticker['bid'] >= limit:
            price = limit
        if price is None:
            continue

        volume = float(row['volume'])
        notional = volume * price
        fee = fees.fee(notional, ordertype)
        fills.append(_apply_fill(sb, row, mode='paper', volume=volume,
                                 price=price, cost=notional, fee=fee))
    return fills


def reconcile_live(sb, *, strategy: str, pair: str) -> list[dict]:
    """Track live orders on Kraken and record their outcomes.

    - 'pending' rows (crash between insert and submit) are recovered by
      userref lookup: adopt the txid if the order reached Kraken, otherwise
      mark failed so the strategy can re-decide.
    - 'submitted'/'open' rows are refreshed via QueryOrders; closed orders
      become fills, canceled/expired orders release their state.
    """
    from bot import kraken_api

    fills = []
    rows = [r for r in db.open_orders(sb, 'live', strategy) if r['pair'] == pair]

    for row in [r for r in rows if r['state'] == 'pending']:
        userref = row.get('userref')
        found = {}
        if userref:
            found = kraken_api.open_orders_by_userref(userref)
            if not found:
                found = kraken_api.closed_orders_by_userref(userref)
        if found:
            txid = next(iter(found))
            db.update_order(sb, row['id'],
                            {'state': 'submitted', 'kraken_txid': txid})
            row['state'], row['kraken_txid'] = 'submitted', txid
            db.log_event(sb, 'warn', 'pending_order_recovered',
                         {'order_id': row['id'], 'txid': txid})
        else:
            db.update_order(sb, row['id'], {
                'state': 'failed',
                'error': 'pending order not found on Kraken (crash before submit)'})
            if row['side'] == 'sell' and row.get('lot_id'):
                db.update_lot(sb, row['lot_id'], {'state': 'open'})
            db.log_event(sb, 'warn', 'pending_order_failed',
                         {'order_id': row['id']})

    tracked = [r for r in rows
               if r['state'] in ('submitted', 'open') and r.get('kraken_txid')]
    if not tracked:
        return fills
    info_by_txid = kraken_api.query_orders([r['kraken_txid'] for r in tracked])

    for row in tracked:
        info = info_by_txid.get(row['kraken_txid'])
        if info is None:
            db.log_event(sb, 'error', 'order_missing_on_kraken',
                         {'order_id': row['id'], 'txid': row['kraken_txid']})
            continue
        status = info.get('status')
        vol_exec = float(info.get('vol_exec') or 0)
        cost = float(info.get('cost') or 0)
        fee = float(info.get('fee') or 0)
        avg_price = float(info.get('price') or 0)
        if not avg_price and vol_exec:
            avg_price = cost / vol_exec

        if status in ('pending', 'open'):
            if row['state'] != 'open':
                db.update_order(sb, row['id'], {'state': 'open'})
        elif status == 'closed':
            fills.append(_apply_fill(sb, row, mode='live', volume=vol_exec,
                                     price=avg_price, cost=cost, fee=fee))
        elif status in ('canceled', 'expired'):
            if vol_exec > 0 and row['side'] == 'buy':
                # Partially filled buy then canceled: keep what we bought.
                fills.append(_apply_fill(sb, row, mode='live', volume=vol_exec,
                                         price=avg_price, cost=cost, fee=fee))
            elif vol_exec > 0:
                # Partially filled sell then canceled: the lot is now split
                # between sold and held — flag for a human, don't guess.
                db.update_order(sb, row['id'],
                                {'state': 'canceled',
                                 'error': f'partial sell fill {vol_exec}'})
                db.log_event(sb, 'error', 'partial_sell_canceled',
                             {'order_id': row['id'], 'lot_id': row.get('lot_id'),
                              'vol_exec': vol_exec,
                              'note': 'manual lot adjustment required'})
            else:
                db.update_order(sb, row['id'], {'state': 'canceled'})
                if row['side'] == 'sell' and row.get('lot_id'):
                    db.update_lot(sb, row['lot_id'], {'state': 'open'})
    return fills


def submit_live(sb, order_row: dict, config: dict) -> None:
    """Submit a real order to Kraken. Double-gated; validate-only by default."""
    if not live_gate_open(config):
        db.update_order(sb, order_row['id'],
                        {'state': 'failed', 'error': 'live gate closed '
                         '(need ALLOW_LIVE=1 and strategy_config.confirm_live=true)'})
        db.log_event(sb, 'error', 'live_gate_closed', {'order_id': order_row['id']})
        return

    from bot import kraken_api
    decimals = PAIR_PRICE_DECIMALS.get(order_row['pair'], 1)
    body = {
        'pair': order_row['pair'],
        'type': order_row['side'],
        'ordertype': order_row['ordertype'],
        'volume': f"{float(order_row['volume']):.8f}",
        'userref': order_row['id'] % 2_147_483_647,
    }
    if order_row['ordertype'] == 'limit':
        body['price'] = f"{float(order_row['price']):.{decimals}f}"
        body['oflags'] = 'post'  # post-only: maker or rejected, never taker
    if config.get('live_validate_only', True):
        body['validate'] = True
    try:
        result = kraken_api.private('/0/private/AddOrder', body)
        if config.get('live_validate_only', True):
            db.update_order(sb, order_row['id'],
                            {'state': 'canceled', 'error': 'validate-only mode'})
            if order_row['side'] == 'sell' and order_row.get('lot_id'):
                db.update_lot(sb, order_row['lot_id'], {'state': 'open'})
        else:
            txid = result['txid'][0]
            db.update_order(sb, order_row['id'],
                            {'state': 'submitted', 'kraken_txid': txid})
    except Exception as exc:  # noqa: BLE001 - persist any submit failure
        db.update_order(sb, order_row['id'],
                        {'state': 'failed', 'error': str(exc)[:500]})
        if order_row['side'] == 'sell' and order_row.get('lot_id'):
            db.update_lot(sb, order_row['lot_id'], {'state': 'open'})
        db.log_event(sb, 'error', 'order_submit_failed',
                     {'order_id': order_row['id'], 'error': str(exc)[:500]})
