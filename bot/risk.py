"""Risk manager: hard guardrails between strategy intents and execution."""

from datetime import datetime, timezone

import pandas as pd

from bot import db
from bot.models import Intent

MAX_CANDLE_AGE_DAYS = 3  # daily candles: tolerate up to 2 missed cycles + lag


def data_fresh(candles: pd.DataFrame) -> bool:
    age = datetime.now(timezone.utc) - candles['ts'].iloc[-1]
    return age.days < MAX_CANDLE_AGE_DAYS


def peak_equity(sb, mode: str) -> float:
    rows = (sb.table('equity_snapshots').select('cash_usd,inventory_value_usd')
            .eq('mode', mode).execute().data)
    if not rows:
        return 0.0
    return max(float(r['cash_usd']) + float(r['inventory_value_usd']) for r in rows)


def filter_intents(sb, intents: list[Intent], *, mode: str, config: dict,
                   portfolio, broker, equity: float) -> list[Intent]:
    """Veto intents that would breach a guardrail. Sells are never vetoed
    (reducing risk is always allowed); buys must pass every check."""
    allowed: list[Intent] = []
    budget = float(config.get('budget_usd', 500))
    max_lots = int(config.get('max_open_lots', 10))
    max_orders = int(config.get('max_orders_per_day', 12))
    max_dd = config.get('max_drawdown_pct')

    n_today = db.orders_today(sb, mode)
    open_lots = len(portfolio.open_lots())
    reserved = broker.reserved_buy_usd()
    peak = max(peak_equity(sb, mode), equity)
    dd_breached = (max_dd is not None and peak > 0
                   and equity < peak * (1 - float(max_dd) / 100))
    if dd_breached:
        db.log_event(sb, 'error', 'drawdown_guard',
                     {'equity': round(equity, 2), 'peak': round(peak, 2),
                      'max_dd_pct': max_dd, 'action': 'buys blocked'})

    for intent in intents:
        if intent.side == 'sell':
            allowed.append(intent)
            continue
        notional = intent.volume * (intent.price or 0)
        veto = None
        if dd_breached:
            veto = 'drawdown_guard'
        elif portfolio.deployed_usd() + reserved + notional > budget * 1.001:
            veto = 'budget_cap'
        elif open_lots >= max_lots:
            veto = 'max_open_lots'
        elif n_today + len(allowed) >= max_orders:
            veto = 'max_orders_per_day'
        if veto:
            db.log_event(sb, 'warn', 'intent_vetoed',
                         {'veto': veto, 'side': intent.side,
                          'notional': round(notional, 2), 'reason': intent.reason})
        else:
            allowed.append(intent)
            reserved += notional
    return allowed
