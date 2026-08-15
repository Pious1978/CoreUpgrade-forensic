from decimal import Decimal

class LiquidityEngine:
    def __init__(self, default_liquidity: Decimal = Decimal("1000000")):
        self.default_liquidity = default_liquidity

    def get_available_liquidity(self, symbol: str, order_quantity: Decimal) -> Decimal:
        return max(Decimal("0"), self.default_liquidity)
