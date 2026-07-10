"""Monitoring: equity snapshots + email alerts for error-severity events."""

import json
from datetime import datetime, timezone

from bot import db, executor, notify
from bot.ticker import PAIR_ASSET


def snapshot_and_alert(sb, *, mode: str, strategy: str, pair: str,
                       tick: dict, config: dict) -> None:
    portfolio = executor.load_portfolio(sb, mode, strategy,
                                        float(config.get('budget_usd', 500)))
    price = tick['last']
    inventory = portfolio.inventory_volume() * price
    unrealized = inventory - portfolio.deployed_usd()
    db.snapshot(sb, mode=mode, cash=portfolio.cash_usd, inventory=inventory,
                unrealized=unrealized, realized=portfolio.realized_cum_usd,
                fees=portfolio.fees_cum_usd, n_lots=len(portfolio.open_lots()))
    _alert_new_errors(sb)


def _alert_new_errors(sb) -> None:
    """Email error-severity events created since the last alert watermark."""
    config = db.load_config(sb)
    watermark = config.get('last_alert_ts') or '1970-01-01T00:00:00+00:00'
    events = (sb.table('bot_events').select('*').eq('severity', 'error')
              .gt('ts', watermark).order('ts').execute().data)
    if not events:
        return
    if not notify.configured():
        # Surface once per batch in the event log; GH Actions logs show it too.
        print(f'{len(events)} error event(s) but SMTP_APP_PASSWORD not set')
        return
    lines = [f"{e['ts']}  {e['kind']}  {json.dumps(e.get('detail'))}"
             for e in events]
    ok = notify.send(
        subject=f"{len(events)} error event(s)",
        body='\n'.join(lines))
    if ok:
        sb.table('strategy_config').upsert({
            'key': 'last_alert_ts',
            'value': json.dumps(events[-1]['ts']),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }, on_conflict='key').execute()
