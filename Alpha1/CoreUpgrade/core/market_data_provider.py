"""
core/market_data_provider.py
-------------------------------------------------------------------------
Modular Live Market Data & Intraday RVOL Provider
"""

import os
import yfinance as yf
import pandas as pd
from core.config import PARQUET_CACHE_DIR

class MarketDataProvider:
    @staticmethod
    def get_live_quote(ticker: str) -> dict:
        """
        Fetches real-time 5-minute intraday quotes and calculates intraday RVOL.
        Falls back gracefully to EOD parquet cache if live connection fails.
        """
        clean_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        try:
            # Fetch intraday 5m data for the current session
            df_intra = yf.download(clean_ticker, period="1d", interval="5m", progress=False)
            if df_intra.empty or len(df_intra) < 2:
                return MarketDataProvider._fallback_to_cache(ticker)
            
            # Flatten multi-index columns if present
            if isinstance(df_intra.columns, pd.MultiIndex):
                df_intra.columns = [col[0].lower() for col in df_intra.columns]
            else:
                df_intra.columns = [c.lower() for c in df_intra.columns]

            curr_px = float(df_intra['close'].iloc[-1])
            curr_vol = float(df_intra['volume'].iloc[-1])
            
            # Intraday slot average volume (using mean of previous 5m bars today as baseline)
            avg_slot_vol = float(df_intra['volume'].iloc[:-1].mean()) if len(df_intra) > 5 else curr_vol
            rvol = round(curr_vol / avg_slot_vol, 2) if avg_slot_vol > 0 else 1.0

            return {
                "price": curr_px,
                "volume": curr_vol,
                "rvol": rvol,
                "source": "LIVE_INTRADAY_5M"
            }
        except Exception:
            return MarketDataProvider._fallback_to_cache(ticker)

    @staticmethod
    def _fallback_to_cache(ticker: str) -> dict:
        clean_ticker = ticker.replace(".NS", "")
        path = os.path.join(PARQUET_CACHE_DIR, f"{clean_ticker}.parquet")
        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    curr_px = float(df['close'].iloc[-1])
                    curr_vol = float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0.0
                    avg_vol = float(df['volume'].iloc[-21:-1].mean()) if 'volume' in df.columns and len(df) >= 21 else 1.0
                    rvol = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                    return {"price": curr_px, "volume": curr_vol, "rvol": rvol, "source": "PARQUET_CACHE_FALLBACK"}
            except Exception:
                pass
        return {"price": 0.0, "volume": 0.0, "rvol": 1.0, "source": "NONE"}
