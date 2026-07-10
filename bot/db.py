"""Supabase access layer for the bot: config, orders, lots, events, snapshots."""

import json
import os
from datetime import datetime, timezone

import dotenv
from supabase import Client, create_client


def client() -> Client:
    dotenv.load_dotenv()
    return create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])


def load_config(sb: Client) -> dict:
    rows = sb.table('strategy_config').select('key,value').execute().data
    return {r['key']: r['value'] for r in rows}


def log_event(sb: Client, severity: str, kind: str, detail: dict | None = None) -> None:
    print(f'[{severity}] {kind}: {json.dumps(detail) if detail else ""}')
    sb.table('bot_events').insert(
        {'severity': severity, 'kind': kind, 'detail': detail}).execute()


# -- orders ------------------------------------------------------------------

def insert_order(sb: Client, *, mode: str, strategy: str, pair: str, side: str,
                 ordertype: str, price: float | None, volume: float,
                 lot_id: int | None = None, reason: str = '') -> dict:
    row = sb.table('orders').insert({
        'mode': mode, 'strategy': strategy, 'pair': pair, 'side': side,
        'ordertype': ordertype, 'price': price, 'volume': volume,
        'lot_id': lot_id, 'reason': reason, 'state': 'pending',
    }).execute().data[0]
    # userref doubles as the idempotency key sent to Kraken (int32).
    sb.table('orders').update({'userref': row['id'] % 2_147_483_647}) \
        .eq('id', row['id']).execute()
    return row


def update_order(sb: Client, order_id: int, fields: dict) -> None:
    fields = {**fields, 'updated_at': datetime.now(timezone.utc).isoformat()}
    sb.table('orders').update(fields).eq('id', order_id).execute()


def open_orders(sb: Client, mode: str, strategy: str | None = None) -> list[dict]:
    q = (sb.table('orders').select('*').eq('mode', mode)
         .in_('state', ['pending', 'submitted', 'open']))
    if strategy:
        q = q.eq('strategy', strategy)
    return q.execute().data


def orders_today(sb: Client, mode: str) -> int:
    start = datetime.now(timezone.utc).strftime('%Y-%m-%dT00:00:00+00:00')
    rows = (sb.table('orders').select('id').eq('mode', mode)
            .gte('created_at', start).execute().data)
    return len(rows)


# -- lots ---------------------------------------------------------------------

def insert_lot(sb: Client, *, mode: str, strategy: str, asset: str,
               volume: float, cost_usd: float, fee_usd: float,
               buy_order_id: int | None, target_price: float | None,
               opened_at: str, base_ledger_id: str | None = None) -> dict:
    return sb.table('lots').insert({
        'mode': mode, 'strategy': strategy, 'asset': asset, 'volume': volume,
        'cost_usd': cost_usd, 'fee_usd': fee_usd, 'buy_order_id': buy_order_id,
        'target_price': target_price, 'opened_at': opened_at, 'state': 'open',
        'base_ledger_id': base_ledger_id,
    }).execute().data[0]


def update_lot(sb: Client, lot_id: int, fields: dict) -> None:
    sb.table('lots').update(fields).eq('id', lot_id).execute()


def lots(sb: Client, mode: str, strategy: str | None = None,
         states: list[str] | None = None) -> list[dict]:
    q = sb.table('lots').select('*').eq('mode', mode)
    if strategy:
        q = q.eq('strategy', strategy)
    if states:
        q = q.in_('state', states)
    return q.execute().data


def snapshot(sb: Client, *, mode: str, cash: float, inventory: float,
             unrealized: float, realized: float, fees: float, n_lots: int) -> None:
    sb.table('equity_snapshots').upsert({
        'ts': datetime.now(timezone.utc).isoformat(), 'mode': mode,
        'cash_usd': round(cash, 2), 'inventory_value_usd': round(inventory, 2),
        'unrealized_usd': round(unrealized, 2),
        'realized_cum_usd': round(realized, 2), 'fees_cum_usd': round(fees, 2),
        'open_lots': n_lots,
    }, on_conflict='ts,mode').execute()
