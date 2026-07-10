"""Event-driven, lot-based backtest engine.

Conservative fill rules (no lookahead):
  - Orders placed while processing candle t are eligible from candle t+1.
  - Limit buy fills if candle.low <= limit price; fill AT the limit price.
  - Limit sell fills if candle.high >= limit price; fill AT the limit price.
  - Market orders fill at the next candle's open +/- slippage_bps.
  - Limit orders expire after `ttl` candles (strategy decides to re-place).

The portfolio accounting (bot.models.Portfolio) is the same implementation
the paper/live executor uses.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from bot.models import Candle, FeeModel, Intent, Portfolio


@dataclass
class OpenOrder:
    id: int
    side: str                 # buy | sell
    ordertype: str            # limit | market
    volume: float
    price: Optional[float]
    lot_id: Optional[int]
    reason: str
    placed_idx: int           # candle index when placed
    ttl: int                  # limit orders: max candles to rest (0 = GTC)


@dataclass
class Fill:
    ts: object
    side: str
    ordertype: str
    volume: float
    price: float
    fee_usd: float
    lot_id: Optional[int]
    reason: str


class Broker:
    """The strategy's view of the engine: open orders + cancellation."""

    def __init__(self, engine: 'Engine'):
        self._engine = engine

    def open_orders(self) -> list[OpenOrder]:
        return list(self._engine.open_orders)

    def cancel(self, order_id: int) -> None:
        self._engine.cancel(order_id)

    def reserved_buy_usd(self) -> float:
        return sum(o.volume * o.price for o in self._engine.open_orders
                   if o.side == 'buy' and o.price is not None)


class Engine:
    def __init__(self, candles: pd.DataFrame, strategy, portfolio: Portfolio,
                 fees: FeeModel | None = None, slippage_bps: float = 5.0,
                 default_ttl: int = 1):
        self.candles = candles.reset_index(drop=True)
        self.strategy = strategy
        self.portfolio = portfolio
        self.fees = fees or FeeModel()
        self.slippage_bps = slippage_bps
        self.default_ttl = default_ttl
        self.open_orders: list[OpenOrder] = []
        self.fills: list[Fill] = []
        self.equity_curve: list[dict] = []
        self._next_order_id = 1

    # -- order management -------------------------------------------------
    def place(self, intent: Intent, idx: int, ttl: int | None = None) -> None:
        order = OpenOrder(
            id=self._next_order_id, side=intent.side, ordertype=intent.ordertype,
            volume=intent.volume, price=intent.price, lot_id=intent.lot_id,
            reason=intent.reason, placed_idx=idx,
            ttl=self.default_ttl if ttl is None else ttl,
        )
        self._next_order_id += 1
        self.open_orders.append(order)
        if intent.side == 'sell' and intent.lot_id is not None:
            lot = self._lot(intent.lot_id)
            if lot is not None:
                lot.state = 'exiting'

    def cancel(self, order_id: int) -> None:
        for o in list(self.open_orders):
            if o.id == order_id:
                self.open_orders.remove(o)
                if o.side == 'sell' and o.lot_id is not None:
                    lot = self._lot(o.lot_id)
                    if lot is not None and lot.state == 'exiting':
                        lot.state = 'open'

    def _lot(self, lot_id: int):
        for lot in self.portfolio.lots:
            if lot.id == lot_id:
                return lot
        return None

    # -- fills -------------------------------------------------------------
    def _execute(self, order: OpenOrder, price: float, candle: Candle, idx: int) -> None:
        notional = order.volume * price
        fee = self.fees.fee(notional, order.ordertype)
        follow_ups: list[Intent] = []
        if order.side == 'buy':
            lot = self.portfolio.open_lot(
                strategy=self.strategy.name, volume=order.volume,
                cost_usd=notional, fee_usd=fee, ts=candle.ts)
            follow_ups = self.strategy.on_buy_fill(lot, candle) or []
        else:
            lot = self._lot(order.lot_id)
            if lot is None or lot.state == 'closed':
                return
            self.portfolio.close_lot(lot, proceeds_usd=notional,
                                     exit_fee_usd=fee, ts=candle.ts)
            follow_ups = self.strategy.on_sell_fill(lot, candle) or []
        self.fills.append(Fill(ts=candle.ts, side=order.side,
                               ordertype=order.ordertype, volume=order.volume,
                               price=price, fee_usd=fee, lot_id=order.lot_id,
                               reason=order.reason))
        for intent in follow_ups:
            self.place(intent, idx, ttl=intent.ttl)

    def _process_fills(self, candle: Candle, idx: int) -> None:
        for order in list(self.open_orders):
            if order.placed_idx >= idx:
                continue  # placed this candle; eligible next candle
            filled = False
            if order.ordertype == 'market':
                slip = candle.open * self.slippage_bps / 10000
                price = candle.open + slip if order.side == 'buy' else candle.open - slip
                self._execute(order, price, candle, idx)
                filled = True
            elif order.side == 'buy' and candle.low <= order.price:
                self._execute(order, order.price, candle, idx)
                filled = True
            elif order.side == 'sell' and candle.high >= order.price:
                self._execute(order, order.price, candle, idx)
                filled = True

            if filled:
                self.open_orders.remove(order)
            elif order.ttl and idx - order.placed_idx >= order.ttl:
                self.cancel(order.id)

    # -- main loop ----------------------------------------------------------
    def run(self) -> 'Engine':
        for idx, row in enumerate(self.candles.itertuples()):
            candle = Candle(ts=row.ts, open=row.open, high=row.high,
                            low=row.low, close=row.close, volume=row.volume)
            self._process_fills(candle, idx)
            intents = self.strategy.on_candle(candle, self.portfolio, Broker(self))
            for intent in intents:
                self.place(intent, idx, ttl=intent.ttl)
            self.equity_curve.append({
                'ts': candle.ts,
                'equity': self.portfolio.equity(candle.close),
                'cash': self.portfolio.cash_usd,
                'deployed': self.portfolio.deployed_usd(),
                'open_lots': len(self.portfolio.open_lots()),
            })
        return self
