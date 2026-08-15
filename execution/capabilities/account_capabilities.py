from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AccountCapabilities:
    allows_shorting: bool = False
    allows_margin: bool = False
    allows_fractional: bool = False
    allows_cancel: bool = True
    allows_stop_orders: bool = True
