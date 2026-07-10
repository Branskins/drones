"""Performance metrics computed from an Engine run."""

import numpy as np
import pandas as pd

from bot.models import FeeModel


def compute_metrics(engine, budget_usd: float) -> dict:
    eq = pd.DataFrame(engine.equity_curve)
    closed = [l for l in engine.portfolio.lots if l.state == 'closed']
    open_lots = engine.portfolio.open_lots()

    equity = eq['equity']
    final_equity = float(equity.iloc[-1])
    net_pnl = final_equity - budget_usd
    years = max((eq['ts'].iloc[-1] - eq['ts'].iloc[0]).days / 365.25, 1e-9)

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    returns = equity.pct_change().dropna()
    periods_per_year = len(eq) / years
    sharpe = 0.0
    if returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(periods_per_year))

    wins = [l for l in closed if (l.realized_usd or 0) > 0]
    holding_days = [
        (l.closed_at - l.opened_at).days for l in closed
        if l.closed_at is not None
    ]

    return {
        'final_equity': round(final_equity, 2),
        'net_pnl': round(net_pnl, 2),
        'return_pct': round(net_pnl / budget_usd * 100, 2),
        'cagr_pct': round(((final_equity / budget_usd) ** (1 / years) - 1) * 100, 2),
        'max_drawdown_pct': round(float(drawdown.min()) * 100, 2),
        'sharpe': round(sharpe, 2),
        'fees_usd': round(engine.portfolio.fees_cum_usd, 2),
        'realized_usd': round(engine.portfolio.realized_cum_usd, 2),
        'unrealized_usd': round(final_equity - budget_usd - engine.portfolio.realized_cum_usd, 2),
        'round_trips': len(closed),
        'win_rate_pct': round(len(wins) / len(closed) * 100, 1) if closed else None,
        'median_holding_days': float(np.median(holding_days)) if holding_days else None,
        'open_lots_end': len(open_lots),
        'utilization_pct': round(float((eq['deployed'] / budget_usd).mean()) * 100, 1),
        'pct_time_fully_invested': round(
            float((eq['deployed'] >= budget_usd * 0.95).mean()) * 100, 1),
    }


def buy_and_hold(candles: pd.DataFrame, budget_usd: float,
                 fees: FeeModel | None = None) -> dict:
    """Benchmark: everything in at the first close (taker), valued at last close."""
    fees = fees or FeeModel()
    entry = candles['open'].iloc[1]  # same no-lookahead convention as the engine
    fee = fees.fee(budget_usd, 'market')
    volume = (budget_usd - fee) / entry
    equity = volume * candles['close']
    running_max = equity.cummax()
    dd = ((equity - running_max) / running_max).min()
    final = float(equity.iloc[-1])
    years = max((candles['ts'].iloc[-1] - candles['ts'].iloc[0]).days / 365.25, 1e-9)
    return {
        'final_equity': round(final, 2),
        'net_pnl': round(final - budget_usd, 2),
        'return_pct': round((final - budget_usd) / budget_usd * 100, 2),
        'cagr_pct': round(((final / budget_usd) ** (1 / years) - 1) * 100, 2),
        'max_drawdown_pct': round(float(dd) * 100, 2),
        'fees_usd': round(fee, 2),
    }
