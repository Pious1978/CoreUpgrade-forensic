"""
validation/signal_quality.py
Production-grade signal quality and trade validation engine.
Features: T+1 open execution, gap-aware conservative stop-loss simulation,
clean MFE/MAE handling, signal-to-horizon lineage, flattened audit metadata,
exit dates, stop distance tracking, and independent observation flags.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SignalQualityAnalyzer:
    """Evaluates raw signals against historical price paths to generate

    statistically sound, execution-realistic trade outcomes with transaction costs,
    slippage, audit lineage, and proper sample independence flags.
    """

    def __init__(
        self,
        price_data: pd.DataFrame,
        holding_periods: Optional[List[int]] = None,
        stop_loss: float = 0.08,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> None:
        required_columns = {"date", "open", "high", "low", "close"}
        missing = required_columns - set(price_data.columns)
        if missing:
            raise ValueError(f"Missing required columns in price_data: {missing}")

        self.price_data = price_data.sort_values("date").reset_index(drop=True)
        self.holding_periods = holding_periods if holding_periods is not None else [5, 10, 20, 60]
        self.stop_loss = stop_loss
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

        self.price_data["date"] = pd.to_datetime(self.price_data["date"])

    def evaluate_signals(self, signals: List[Dict[str, Any]]) -> pd.DataFrame:
        evaluated_trades = []

        for sig in signals:
            symbol = sig.get("symbol")
            setup_name = sig.get("setup_name", "UNKNOWN")
            signal_date = pd.to_datetime(sig.get("signal_date"))
            market_regime = sig.get("market_regime", "UNKNOWN")
            signal_id = sig.get("signal_id", str(uuid.uuid4()))

            idx_match = self.price_data.index[self.price_data["date"] == signal_date].tolist()

            if not idx_match:
                logger.warning(f"Signal date {signal_date} not found in price data for {symbol}.")
                continue

            signal_idx = idx_match[0]
            entry_idx = signal_idx + 1

            if entry_idx >= len(self.price_data):
                logger.debug(f"Skipping signal for {symbol}: insufficient future data for T+1 entry.")
                continue

            raw_entry_price = float(self.price_data.loc[entry_idx, "open"])
            entry_price = raw_entry_price * (1.0 + self.slippage_rate)
            entry_date = self.price_data.loc[entry_idx, "date"]

            assert entry_price > 0, f"Invalid entry price {entry_price} for {symbol} on {entry_date}"

            for hp in self.holding_periods:
                exit_idx_target = entry_idx + hp - 1
                if exit_idx_target >= len(self.price_data):
                    exit_idx_target = len(self.price_data) - 1

                future_slice = self.price_data.loc[entry_idx:exit_idx_target]
                if future_slice.empty:
                    continue

                stop_price = entry_price * (1.0 - self.stop_loss)
                trade_status = "OPEN"
                raw_exit_price = entry_price
                exit_reason = "TIME_EXIT"
                actual_exit_idx = entry_idx

                max_high = entry_price
                min_low = entry_price

                for idx, candle in future_slice.iterrows():
                    current_low = float(candle["low"])
                    current_high = float(candle["high"])
                    current_open = float(candle["open"])

                    if current_low < min_low:
                        min_low = current_low
                    if current_high > max_high:
                        max_high = current_high

                    if current_low <= stop_price:
                        trade_status = "STOPPED"
                        if current_open < stop_price:
                            raw_exit_price = current_open
                        else:
                            raw_exit_price = stop_price
                        exit_reason = "STOP_LOSS"
                        actual_exit_idx = idx
                        break

                if trade_status == "OPEN":
                    actual_exit_idx = exit_idx_target
                    raw_exit_price = float(self.price_data.loc[actual_exit_idx, "close"])
                    exit_reason = "TIME_EXIT"

                exit_date = self.price_data.loc[actual_exit_idx, "date"]
                exit_price = raw_exit_price * (1.0 - self.slippage_rate)
                holding_days = int(actual_exit_idx - entry_idx + 1)

                gross_return = (exit_price - entry_price) / entry_price
                net_return = gross_return - (self.commission_rate * 2)

                if trade_status == "STOPPED":
                    if actual_exit_idx > entry_idx:
                        pre_stop_slice = self.price_data.loc[entry_idx : actual_exit_idx - 1]
                        pre_stop_max_high = (
                            float(pre_stop_slice["high"].max())
                            if not pre_stop_slice.empty
                            else entry_price
                        )
                        mfe = max(0.0, (pre_stop_max_high - entry_price) / entry_price)
                    else:
                        mfe = 0.0
                else:
                    mfe = max(0.0, (max_high - entry_price) / entry_price)

                mae = max(0.0, (entry_price - min_low) / entry_price)

                assert not np.isnan(net_return), f"Net return is NaN for {symbol}"
                assert exit_reason in [
                    "STOP_LOSS",
                    "TIME_EXIT",
                    "OPEN",
                ], f"Invalid exit reason: {exit_reason}"

                successful = net_return > 0
                trade_id = str(uuid.uuid4())

                trade_record = {
                    "signal_id": signal_id,
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "setup_name": setup_name,
                    "signal_date": signal_date.strftime("%Y-%m-%d"),
                    "entry_date": pd.to_datetime(entry_date).strftime("%Y-%m-%d"),
                    "exit_date": pd.to_datetime(exit_date).strftime("%Y-%m-%d"),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "exit_reason": exit_reason,
                    "holding_period_target": hp,
                    "holding_days": holding_days,
                    "stop_distance_pct": self.stop_loss,
                    "return_pct": round(net_return, 4),
                    "gross_return_pct": round(gross_return, 4),
                    "mfe": round(mfe, 4),
                    "mae": round(mae, 4),
                    "market_regime": market_regime,
                    "evaluation_type": "holding_period_analysis",
                    "sample_unit": "signal_horizon",
                    "independent_observation": False,
                    "execution_model": "T+1_open",
                    "stop_model": "conservative_gap_aware",
                    "price_frequency": "daily",
                    "successful": successful,
                }

                evaluated_trades.append(trade_record)

        return pd.DataFrame(evaluated_trades)
