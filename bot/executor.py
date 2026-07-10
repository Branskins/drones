"""Order execution + reconciliation.

Paper mode: orders are recorded in the `orders` table and filled against the
live public ticker by `reconcile_paper` on the next cycle — no private Kraken
call is ever made.

Live mode: `submit_live` places real orders via AddOrder. It is double-gated:
config `confirm_live` must be true AND the env var ALLOW_LIVE=1 must be set
(the GitHub Actions workflow does not set it; a human enables it deliberately).
"""

import json
import os
from datetime import datetime, timezone

from bot import db
from bot.models import FeeModel, Intent, Lot
from bot.ticker import PAIR_ASSET


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
        db.update_order(self.sb, order_id, {'state': 'canceled'})
        row = next((r for r in self._rows if r['id'] == order_id), None)
        if row and row['side'] == 'sell' and row.get('lot_id'):
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


def reconcile_paper(sb, *, strategy: str, pair: str, ticker: dict,
                    fees: FeeModel) -> list[dict]:
    """Fill resting paper orders against the live ticker. Returns fill records
    [{'order': row, 'lot': lot_row, 'price': float, 'fee': float}]."""
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
        now = datetime.now(timezone.utc).isoformat()
        db.update_order(sb, row['id'], {
            'state': 'filled', 'filled_volume': volume,
            'avg_fill_price': price, 'fee_usd': round(fee, 6)})

        lot_row = None
        if row['side'] == 'buy':
            lot_row = db.insert_lot(
                sb, mode='paper', strategy=strategy, asset=PAIR_ASSET[pair],
                volume=volume, cost_usd=round(notional, 6),
                fee_usd=round(fee, 6), buy_order_id=row['id'],
                target_price=None, opened_at=now)
        elif row.get('lot_id'):
            db.update_lot(sb, row['lot_id'], {
                'state': 'closed', 'closed_at': now,
                'proceeds_usd': round(notional - fee, 6),
                'sell_order_id': row['id']})
            lot_row = {'id': row['lot_id']}
        fills.append({'order': row, 'lot': lot_row, 'price': price, 'fee': fee})
    return fills


def submit_live(sb, order_row: dict, config: dict) -> None:
    """Submit a real order to Kraken. Double-gated; validate-only by default."""
    if os.environ.get('ALLOW_LIVE') != '1' or config.get('confirm_live') is not True:
        db.update_order(sb, order_row['id'],
                        {'state': 'failed', 'error': 'live gate closed '
                         '(need ALLOW_LIVE=1 and strategy_config.confirm_live=true)'})
        db.log_event(sb, 'error', 'live_gate_closed', {'order_id': order_row['id']})
        return

    from utils.kraken import request
    body = {
        'pair': order_row['pair'],
        'type': order_row['side'],
        'ordertype': order_row['ordertype'],
        'volume': f"{float(order_row['volume']):.8f}",
        'userref': order_row['id'] % 2_147_483_647,
    }
    if order_row['ordertype'] == 'limit':
        body['price'] = f"{float(order_row['price']):.1f}"
        body['oflags'] = 'post'  # post-only: maker or rejected, never taker
    if config.get('live_validate_only', True):
        body['validate'] = True
    try:
        resp = request(method='POST', path='/0/private/AddOrder', body=body,
                       public_key=os.environ['PUBLIC_KEY'],
                       private_key=os.environ['PRIVATE_KEY'],
                       environment='https://api.kraken.com')
        result = json.loads(resp.read())
        if result.get('error'):
            raise ValueError(', '.join(result['error']))
        if config.get('live_validate_only', True):
            db.update_order(sb, order_row['id'],
                            {'state': 'canceled', 'error': 'validate-only mode'})
        else:
            txid = result['result']['txid'][0]
            db.update_order(sb, order_row['id'],
                            {'state': 'submitted', 'kraken_txid': txid})
    except Exception as exc:  # noqa: BLE001 - persist any submit failure
        db.update_order(sb, order_row['id'],
                        {'state': 'failed', 'error': str(exc)[:500]})
        db.log_event(sb, 'error', 'order_submit_failed',
                     {'order_id': order_row['id'], 'error': str(exc)[:500]})
