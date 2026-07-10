"""Shared datatypes: one lot-accounting implementation used by both the
backtest engine and the live/paper executor, so backtest results and
production P&L are computed the same way."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class FeeModel:
    maker_pct: float = 0.25
    taker_pct: float = 0.40

    def fee(self, notional_usd: float, ordertype: str) -> float:
        rate = self.maker_pct if ordertype == 'limit' else self.taker_pct
        return notional_usd * rate / 100


@dataclass
class Intent:
    """What a strategy wants to do. The risk manager may veto or shrink it."""
    side: Literal['buy', 'sell']
    ordertype: Literal['limit', 'market']
    volume: float                 # base asset units
    price: Optional[float] = None  # None for market
    lot_id: Optional[int] = None   # sells reference the lot they close
    reason: str = ''
    ttl: Optional[int] = None      # limit orders: candles to rest (0 = GTC)


@dataclass
class Lot:
    id: int
    strategy: str
    volume: float
    cost_usd: float               # quote spent, excluding fees
    fee_usd: float                # entry fee
    opened_at: datetime
    target_price: Optional[float] = None
    state: Literal['open', 'exiting', 'closed'] = 'open'
    closed_at: Optional[datetime] = None
    proceeds_usd: Optional[float] = None
    exit_fee_usd: float = 0.0

    @property
    def entry_price(self) -> float:
        return self.cost_usd / self.volume

    def breakeven_price(self, exit_fee_pct: float) -> float:
        """Price at which selling nets exactly cost + entry fee."""
        return (self.cost_usd + self.fee_usd) / (self.volume * (1 - exit_fee_pct / 100))

    def target_for_net_gain(self, gain_pct: float, exit_fee_pct: float) -> float:
        return self.breakeven_price(exit_fee_pct) * (1 + gain_pct / 100)

    @property
    def realized_usd(self) -> Optional[float]:
        if self.proceeds_usd is None:
            return None
        return self.proceeds_usd - self.cost_usd - self.fee_usd - self.exit_fee_usd


@dataclass
class Portfolio:
    """Cash + lots for a single pair. All USD."""
    budget_usd: float
    cash_usd: float = 0.0
    lots: list[Lot] = field(default_factory=list)
    realized_cum_usd: float = 0.0
    fees_cum_usd: float = 0.0
    _next_lot_id: int = 1

    def __post_init__(self):
        if self.cash_usd == 0.0:
            self.cash_usd = self.budget_usd

    def open_lots(self) -> list[Lot]:
        return [l for l in self.lots if l.state != 'closed']

    def deployed_usd(self) -> float:
        return sum(l.cost_usd + l.fee_usd for l in self.open_lots())

    def open_lot(self, strategy: str, volume: float, cost_usd: float,
                 fee_usd: float, ts: datetime, target_price: float | None = None) -> Lot:
        lot = Lot(id=self._next_lot_id, strategy=strategy, volume=volume,
                  cost_usd=cost_usd, fee_usd=fee_usd, opened_at=ts,
                  target_price=target_price)
        self._next_lot_id += 1
        self.lots.append(lot)
        self.cash_usd -= cost_usd + fee_usd
        self.fees_cum_usd += fee_usd
        return lot

    def close_lot(self, lot: Lot, proceeds_usd: float, exit_fee_usd: float,
                  ts: datetime) -> None:
        lot.state = 'closed'
        lot.closed_at = ts
        lot.proceeds_usd = proceeds_usd
        lot.exit_fee_usd = exit_fee_usd
        self.cash_usd += proceeds_usd - exit_fee_usd
        self.fees_cum_usd += exit_fee_usd
        self.realized_cum_usd += lot.realized_usd

    def inventory_volume(self) -> float:
        return sum(l.volume for l in self.open_lots())

    def equity(self, price: float) -> float:
        return self.cash_usd + self.inventory_volume() * price
