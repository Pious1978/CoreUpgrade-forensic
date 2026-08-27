from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BrokerCapabilities:
    supports_cancel: bool = True
    supports_shorting: bool = True
    supports_options: bool = False
    supports_margin: bool = True
    supports_fractional: bool = False
    supports_stop_orders: bool = True
