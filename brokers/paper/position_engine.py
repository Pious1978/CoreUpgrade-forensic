from decimal import Decimal
from typing import List, Optional

class PositionEngine:
    def __init__(self):
        self._positions = {}

    def get_position(self, symbol: str) -> Optional[PositionContract]:
        return self._positions.get(symbol)

    def get_all_positions(self) -> List[PositionContract]:
        return list(self._positions.values())

    def apply_execution(self, order, fill_price: Decimal, filled_quantity: Decimal, timestamp: int):
        if filled_quantity <= Decimal("0"):
            return

        symbol = order.symbol
        current = self._positions.get(symbol)
        qty_change = filled_quantity if order.side == OrderSide.BUY else -filled_quantity

        if current:
            new_qty = current.quantity + qty_change
            if new_qty == 0:
                del self._positions[symbol]
                return
            
            if current.quantity > 0 and new_qty > 0 and qty_change > 0:
                avg_price = ((current.quantity * current.average_price) + (filled_quantity * fill_price)) / new_qty
            else:
                avg_price = current.average_price if new_qty > 0 else fill_price

            current.quantity = new_qty
            current.average_price = avg_price
            current.timestamp = timestamp
        else:
            self._positions[symbol] = PositionContract(
                portfolio_id=order.portfolio_id,
                symbol=symbol,
                quantity=qty_change,
                average_price=fill_price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                timestamp=timestamp
            )
