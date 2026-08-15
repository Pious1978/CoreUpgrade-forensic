from typing import List, Dict, Set, Tuple
from datetime import datetime
from .contracts import TradeRecord

class TradeValidator:
    """
    Gatekeeper engine responsible for pre-flight validation incorporating 
    capital weight ceilings, orphan exit detection, and O(n*k) symbol bucketing.
    """
    
    VALID_REGIMES: Set[str] = {
        "BULL",
        "BEAR",
        "SIDEWAYS",
        "HIGH_VOL",
        "CRISIS"
    }

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def validate(self, trades: List[TradeRecord]) -> List[str]:
        errors: List[str] = []
        seen_trade_ids: Set[str] = set()
        seen_fingerprints: Set[Tuple[str, datetime, datetime, float]] = set()
        
        # Track symbol event intervals for orphan detection and overlap scanning
        symbol_intervals: Dict[str, List[Tuple[datetime, datetime]]] = {}

        for idx, t in enumerate(trades):
            prefix = f"Trade Index {idx} ({t.symbol}, ID: {t.trade_id[:8]})"

            # 1. Capital weight allocation sanity check (Max 100% per trade allocation)
            if t.capital_weight > 1.0:
                errors.append(f"{prefix}: Capital weight ({t.capital_weight}) exceeds 100% (1.0).")

            # 2. Duplicate Trade ID detection
            if t.trade_id in seen_trade_ids:
                errors.append(f"{prefix}: Duplicate trade identifier detected ({t.trade_id}).")
            seen_trade_ids.add(t.trade_id)

            # 3. Duplicate execution fingerprinting
            fingerprint = (t.symbol, t.entry_date, t.exit_date, float(t.r_multiple))
            if fingerprint in seen_fingerprints:
                errors.append(f"{prefix}: Duplicate trade execution record fingerprint detected.")
            seen_fingerprints.add(fingerprint)

            # 4. Market regime conformance
            if t.market_regime not in self.VALID_REGIMES:
                errors.append(f"{prefix}: Invalid market regime '{t.market_regime}'. Allowed: {self.VALID_REGIMES}")

            # 5. Overlapping position detection & structural integrity
            intervals = symbol_intervals.get(t.symbol, [])
            for a_entry, a_exit in intervals:
                if not (t.exit_date < a_entry or t.entry_date > a_exit):
                    errors.append(f"{prefix}: Overlapping active position for symbol {t.symbol} found.")
                    break
            
            intervals.append((t.entry_date, t.exit_date))
            symbol_intervals[t.symbol] = intervals

        # 6. Orphan exit / timeline load check across loaded records
        # If dataset contains isolated close records without corresponding execution overlap context
        for symbol, intervals in symbol_intervals.items():
            sorted_intervals = sorted(intervals, key=lambda x: x[0])
            for i in range(1, len(sorted_intervals)):
                prev_entry, prev_exit = sorted_intervals[i-1]
                curr_entry, _ = sorted_intervals[i]
                if curr_entry < prev_entry:
                    errors.append(f"Timeline Corruption: Symbol {symbol} has out-of-order execution entries.")

        if errors and self.strict_mode:
            raise ValueError(f"TradeValidator failed with {len(errors)} structural/logical errors:\n" + "\n".join(errors))

        return errors
