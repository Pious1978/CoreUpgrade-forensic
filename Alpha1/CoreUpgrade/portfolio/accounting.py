from typing import List, Tuple
from types import MappingProxyType
from uuid import uuid4
from portfolio.snapshot import PortfolioSnapshot, Position
from contracts.base_contract import BaseContract
from contracts.accounting import TradeFillContract, PortfolioLedgerEntry

class PortfolioAccountingEngine:
    """Processes trade fills, updates cost basis and cash, logs ledger entries, and spawns successor snapshots."""

    def apply_fill(self, current_snapshot: PortfolioSnapshot, fill: TradeFillContract) -> Tuple[PortfolioSnapshot, List[PortfolioLedgerEntry]]:
        ledger_entries = []
        new_holdings = dict(current_snapshot.holdings)
        
        symbol = fill.symbol
        qty_change = fill.quantity if fill.side.upper() == "BUY" else -fill.quantity
        gross_cost = fill.quantity * fill.fill_price
        total_cost = gross_cost + fill.fees
        
        cash_change = -total_cost if fill.side.upper() == "BUY" else (gross_cost - fill.fees)

        # Update position cost basis and share quantity
        existing_pos = new_holdings.get(symbol)
        if fill.side.upper() == "BUY":
            if existing_pos:
                new_shares = existing_pos.shares + fill.quantity
                total_spent = (existing_pos.shares * existing_pos.average_cost) + total_cost
                new_avg_cost = total_spent / new_shares if new_shares > 0 else 0.0
                new_holdings[symbol] = Position(
                    symbol=symbol,
                    shares=new_shares,
                    average_cost=new_avg_cost,
                    last_price=fill.fill_price
                )
            else:
                new_holdings[symbol] = Position(
                    symbol=symbol,
                    shares=fill.quantity,
                    average_cost=total_cost / fill.quantity if fill.quantity > 0 else 0.0,
                    last_price=fill.fill_price
                )
        else:  # SELL
            if existing_pos:
                new_shares = max(0.0, existing_pos.shares - fill.quantity)
                if new_shares == 0:
                    del new_holdings[symbol]
                else:
                    new_holdings[symbol] = Position(
                        symbol=symbol,
                        shares=new_shares,
                        average_cost=existing_pos.average_cost,
                        last_price=fill.fill_price
                    )

        # Create audit ledger entry
        entry = PortfolioLedgerEntry(
            portfolio_id=current_snapshot.portfolio_id,
            symbol=symbol,
            transaction_type=fill.side.upper(),
            quantity_change=qty_change,
            cash_change=cash_change,
            reference_trade_id=fill.trade_id
        )
        ledger_entries.append(entry)

        new_cash = current_snapshot.cash_balance + cash_change

        # Spawn immutable successor snapshot (Version + 1, Lineage linked)
        successor_snapshot = PortfolioSnapshot(
            portfolio_id=current_snapshot.portfolio_id,
            snapshot_id=uuid4(),
            previous_snapshot_id=current_snapshot.snapshot_id,
            version=current_snapshot.version + 1,
            root_contract_id=current_snapshot.root_contract_id,
            correlation_id=current_snapshot.correlation_id,
            capital_base=current_snapshot.capital_base,
            cash_balance=round(new_cash, 2),
            holdings=MappingProxyType(new_holdings)
        )

        print(f"\n--- VSC 3.6 Portfolio Accounting Ledger Event ---")
        print(f"Transaction: {fill.side} {fill.quantity} {symbol} @ ₹{fill.fill_price:,.2f} (Fees: ₹{fill.fees:,.2f})")
        print(f"Updated Cash Balance: ₹{successor_snapshot.cash_balance:,.2f}")
        print(f"Snapshot Lineage: v{current_snapshot.version} (ID: {str(current_snapshot.snapshot_id)[:8]}...) ──► v{successor_snapshot.version} (ID: {str(successor_snapshot.snapshot_id)[:8]}...)")
        print("-" * 52)

        return successor_snapshot, ledger_entries
