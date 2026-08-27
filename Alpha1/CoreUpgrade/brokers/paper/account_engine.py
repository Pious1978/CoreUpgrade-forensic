from decimal import Decimal
from .contracts import ExecutionReportContract

class AccountEngine:
    def __init__(self, initial_cash: Decimal, leverage: Decimal = Decimal("5")):
        self.cash_balance = Decimal(str(initial_cash))
        self.leverage = Decimal(str(leverage))

    @property
    def buying_power(self) -> Decimal:
        return self.cash_balance * self.leverage

    def apply_execution(self, execution_report: ExecutionReportContract, side, price: Decimal, quantity: Decimal):
        if quantity <= Decimal("0"):
            return
        trade_value = quantity * price
        if side == OrderSide.BUY:
            self.cash_balance -= trade_value
        elif side == OrderSide.SELL:
            self.cash_balance += trade_value

    def get_account_contract(self) -> AccountContract:
        return AccountContract(
            cash_balance=self.cash_balance,
            buying_power=self.buying_power
        )
