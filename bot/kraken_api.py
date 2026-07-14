"""Thin wrapper over utils.kraken.request for the bot's private API calls.

Uses the bot-dedicated key from PUBLIC_KEY / PRIVATE_KEY (in CI these come
from the KRAKEN_BOT_* secrets). Only order-management endpoints are wrapped —
the key itself must have no withdrawal rights (docs/human-actions.md item 5).
"""

import json
import os

import dotenv

from utils.kraken import request


def private(path: str, body: dict | None = None) -> dict:
    """POST a private endpoint; returns the `result` dict or raises ValueError."""
    dotenv.load_dotenv()  # no-op in CI (secrets come in as real env vars)
    resp = request(
        method='POST', path=path, body=body or {},
        public_key=os.environ['PUBLIC_KEY'],
        private_key=os.environ['PRIVATE_KEY'],
        environment='https://api.kraken.com',
    )
    data = json.loads(resp.read())
    if data.get('error'):
        raise ValueError(', '.join(data['error']))
    return data.get('result', {})


def query_orders(txids: list[str]) -> dict:
    """Order info keyed by txid (max 50 per call)."""
    out: dict = {}
    for i in range(0, len(txids), 50):
        out.update(private('/0/private/QueryOrders',
                           {'txid': ','.join(txids[i:i + 50])}))
    return out


def open_orders_by_userref(userref: int) -> dict:
    result = private('/0/private/OpenOrders', {'userref': userref})
    return result.get('open', {})


def closed_orders_by_userref(userref: int) -> dict:
    result = private('/0/private/ClosedOrders', {'userref': userref})
    return result.get('closed', {})


def cancel_order(txid: str) -> dict:
    return private('/0/private/CancelOrder', {'txid': txid})
