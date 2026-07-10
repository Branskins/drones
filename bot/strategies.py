"""The three candidate strategies from the plan, sharing one interface.

All take-profit targets are NET of fees: `tp_pct` means the lot's realized
gain after entry+exit fees is at least tp_pct. Entries are post-only-style
limit orders at the candle close (maker fee), re-attempted on the strategy's
cadence when unfilled. Exits are resting GTC limit sells (maker fee).
"""

from collections import deque
from datetime import timedelta

from bot.models import Candle, FeeModel, Intent, Lot, Portfolio

# Cash headroom so a batch-sized limit buy plus its maker fee always clears.
FEE_HEADROOM = 1.01


class Strategy:
    name = 'base'

    def __init__(self, params: dict, fees: FeeModel | None = None):
        self.params = params
        self.fees = fees or FeeModel()

    # -- hooks -------------------------------------------------------------
    def on_candle(self, candle: Candle, portfolio: Portfolio, broker) -> list[Intent]:
        raise NotImplementedError

    def on_buy_fill(self, lot: Lot, candle: Candle) -> list[Intent]:
        """Default: set the lot's net take-profit and rest a GTC sell there."""
        tp = self.params.get('tp_pct', 4.0)
        lot.target_price = lot.target_for_net_gain(tp, self.fees.maker_pct)
        return [Intent(side='sell', ordertype='limit', volume=lot.volume,
                       price=lot.target_price, lot_id=lot.id,
                       reason=f'{self.name}:tp', ttl=0)]

    def on_sell_fill(self, lot: Lot, candle: Candle) -> list[Intent]:
        return []

    def hydrate(self, **state) -> None:
        """Restore private state for a stateless (cron) run, e.g.
        hydrate(last_entry_ts=..., closes=[...], initialized=True)."""
        for key, value in state.items():
            attr = f'_{key}'
            if not hasattr(self, attr):
                continue
            current = getattr(self, attr)
            if isinstance(current, deque):
                current.clear()
                current.extend(value)
            else:
                setattr(self, attr, value)

    # -- helpers -----------------------------------------------------------
    def _available_usd(self, portfolio: Portfolio, broker) -> float:
        return portfolio.cash_usd - broker.reserved_buy_usd()

    def _can_buy(self, batch_usd: float, portfolio: Portfolio, broker) -> bool:
        # Orders are sized to batch/FEE_HEADROOM so cost + maker fee always
        # fits inside batch_usd; requiring `batch_usd` cash is sufficient.
        budget = self.params['budget_usd']
        if portfolio.deployed_usd() + broker.reserved_buy_usd() + batch_usd > budget * 1.0001:
            return False
        return self._available_usd(portfolio, broker) >= batch_usd

    def _entry_intent(self, batch_usd: float, price: float, reason: str,
                      ttl: int = 1) -> Intent:
        return Intent(side='buy', ordertype='limit',
                      volume=batch_usd / FEE_HEADROOM / price, price=price,
                      reason=reason, ttl=ttl)


class DcaTakeProfit(Strategy):
    """S1 — the baseline formalized: fixed-cadence DCA, net take-profit."""
    name = 'dca_tp'

    def __init__(self, params: dict, fees: FeeModel | None = None):
        super().__init__(params, fees)
        self._last_entry_ts = None

    def on_candle(self, candle, portfolio, broker) -> list[Intent]:
        interval = timedelta(hours=self.params.get('interval_hours', 72))
        batch = self.params['batch_usd']
        if self._last_entry_ts is not None and candle.ts - self._last_entry_ts < interval:
            return []
        if any(o.side == 'buy' for o in broker.open_orders()):
            return []
        if not self._can_buy(batch, portfolio, broker):
            return []
        self._last_entry_ts = candle.ts
        return [self._entry_intent(batch, candle.close, f'{self.name}:dca')]


class DcaDip(Strategy):
    """S2 — dip-scaled DCA with trend filter and inventory recycling."""
    name = 'dca_dip'

    def __init__(self, params: dict, fees: FeeModel | None = None):
        super().__init__(params, fees)
        self._last_entry_ts = None
        self._closes = deque(maxlen=int(params.get('sma_days', 30)))
        self._peak_equity = 0.0
        self._halted = False

    def _multiplier(self, close: float) -> int:
        if len(self._closes) < self._closes.maxlen:
            return 1  # not enough history: behave like plain DCA
        sma = sum(self._closes) / len(self._closes)
        premium = close / sma - 1
        tiers = self.params.get('tiers', [[0.05, 0], [0.0, 1], [-0.05, 2], [-0.15, 3]])
        for threshold, mult in tiers:
            if premium >= threshold:
                return int(mult)
        return int(tiers[-1][1])

    def on_candle(self, candle, portfolio, broker) -> list[Intent]:
        self._closes.append(candle.close)
        intents: list[Intent] = []

        # Optional portfolio stop: liquidate and halt on deep equity drawdown.
        max_dd = self.params.get('max_dd_pct')
        equity = portfolio.equity(candle.close)
        self._peak_equity = max(self._peak_equity, equity)
        if self._halted:
            return []
        if max_dd and self._peak_equity > 0 and equity < self._peak_equity * (1 - max_dd / 100):
            self._halted = True
            for order in broker.open_orders():
                broker.cancel(order.id)
            return [Intent(side='sell', ordertype='market', volume=lot.volume,
                           lot_id=lot.id, reason=f'{self.name}:stop')
                    for lot in portfolio.open_lots()]

        # Inventory recycling: aging lots get their target cut to ~breakeven.
        max_age = self.params.get('max_age_days', 45)
        recycle_tp = self.params.get('recycle_tp_pct', 0.5)
        sell_orders = {o.lot_id: o for o in broker.open_orders() if o.side == 'sell'}
        for lot in portfolio.open_lots():
            age = (candle.ts - lot.opened_at).days
            if age >= max_age:
                new_target = lot.target_for_net_gain(recycle_tp, self.fees.maker_pct)
                if lot.target_price and new_target < lot.target_price - 1e-9:
                    order = sell_orders.get(lot.id)
                    if order is not None:
                        broker.cancel(order.id)
                    lot.target_price = new_target
                    intents.append(Intent(side='sell', ordertype='limit',
                                          volume=lot.volume, price=new_target,
                                          lot_id=lot.id,
                                          reason=f'{self.name}:recycle', ttl=0))

        # Dip-scaled entry.
        interval = timedelta(hours=self.params.get('interval_hours', 72))
        due = (self._last_entry_ts is None
               or candle.ts - self._last_entry_ts >= interval)
        if due and not any(o.side == 'buy' for o in broker.open_orders()):
            mult = self._multiplier(candle.close)
            batch = self.params['batch_usd'] * mult
            if mult > 0:
                # Cap to whatever budget remains.
                budget_left = (self.params['budget_usd'] - portfolio.deployed_usd()
                               - broker.reserved_buy_usd())
                batch = min(batch, budget_left)
                if batch >= self.params['batch_usd'] * 0.99 and \
                        self._available_usd(portfolio, broker) >= batch:
                    self._last_entry_ts = candle.ts
                    intents.append(self._entry_intent(batch, candle.close,
                                                      f'{self.name}:dip x{mult}'))
            else:
                self._last_entry_ts = candle.ts  # trend filter says skip this cycle
        return intents


class Grid(Strategy):
    """S3 — static grid: resting limit buys at rungs below the anchor price;
    each fill immediately rests its paired sell one step up."""
    name = 'grid'

    def __init__(self, params: dict, fees: FeeModel | None = None):
        super().__init__(params, fees)
        self._initialized = False

    def _rung_prices(self, anchor: float) -> list[float]:
        step = self.params.get('step_pct', 4.0) / 100
        band = self.params.get('band_pct', 25) / 100
        max_rungs = int(self.params['budget_usd'] // self.params['batch_usd'])
        prices = []
        price = anchor
        while len(prices) < max_rungs:
            price *= (1 - step)
            if price < anchor * (1 - band):
                break
            prices.append(price)
        return prices

    def on_candle(self, candle, portfolio, broker) -> list[Intent]:
        if self._initialized:
            return []
        self._initialized = True
        batch = self.params['batch_usd']
        return [self._entry_intent(batch, rung, f'{self.name}:rung', ttl=0)
                for rung in self._rung_prices(candle.close)]

    def on_buy_fill(self, lot: Lot, candle: Candle) -> list[Intent]:
        step = self.params.get('step_pct', 4.0) / 100
        # Sell one step above the rung, but never below the net-gain floor.
        floor = lot.target_for_net_gain(
            self.params.get('min_net_pct', 0.5), self.fees.maker_pct)
        lot.target_price = max(lot.entry_price * (1 + step), floor)
        return [Intent(side='sell', ordertype='limit', volume=lot.volume,
                       price=lot.target_price, lot_id=lot.id,
                       reason=f'{self.name}:tp', ttl=0)]

    def on_sell_fill(self, lot: Lot, candle: Candle) -> list[Intent]:
        # Cycle complete: re-arm the rung this lot was bought at.
        return [self._entry_intent(self.params['batch_usd'], lot.entry_price,
                                   f'{self.name}:rearm', ttl=0)]


REGISTRY = {cls.name: cls for cls in (DcaTakeProfit, DcaDip, Grid)}
