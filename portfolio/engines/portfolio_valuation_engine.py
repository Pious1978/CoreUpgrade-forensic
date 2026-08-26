from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from portfolio.contracts.holdings_snapshot_contract import HoldingsSnapshotContract


@dataclass(frozen=True, slots=True)
class PortfolioValuationEngine:
    """
    Computes authoritative portfolio net value from real account state.

    Formula (identical to the proven legacy path,
    portfolio/snapshot.py::PortfolioSnapshot.total_portfolio_value):

        total_value = cash_balance + sum(holding.quantity * current_price[holding.symbol])

    Current prices must be supplied explicitly by the caller (e.g. the same
    asset_prices mapping already passed to PortfolioBuilder.build() for the
    same rebalance cycle). This engine does not fetch prices from any source;
    no live market-data feed is connected to the canonical spine today. That
    remains a separate, explicit gap.
    """

    def compute_total_value(
        self,
        holdings_snapshot: HoldingsSnapshotContract,
        current_prices: Mapping[str, Decimal],
    ) -> Decimal:
        holdings_value = Decimal("0")
        for holding in holdings_snapshot.holdings:
            if holding.symbol not in current_prices:
                raise ValueError(
                    f"No current price supplied for held symbol '{holding.symbol}'; "
                    f"cannot compute authoritative portfolio value."
                )
            holdings_value += holding.quantity * current_prices[holding.symbol]

        return holdings_snapshot.cash_balance + holdings_value