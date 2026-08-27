"""
Data_Service.py
-------------------------------------------------------------------------
Enterprise Data Layer Service: Caches responses and flattens tickers.
"""
import time
import pandas as pd
import yfinance as yf

class DataService:
    def __init__(self):
        self._price_cache = {}
        self._nifty_cache = None

    def get_nifty_history(self) -> pd.DataFrame:
        """Fetches and caches NIFTY index data for cross-sectional tracking."""
        if self._nifty_cache is not None:
            return self._nifty_cache
            
        df = yf.download("^NSEI", period="1y", progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        self._nifty_cache = df.dropna()
        return self._nifty_cache

    def get_price_history(self, symbol: str) -> pd.DataFrame:
        """Retrieves asset historical bars with in-memory persistence caching."""
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        try:
            df = yf.download(symbol, period="1y", interval="1d", progress=False, threads=False)
            if df.empty:
                return pd.DataFrame()
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            clean_df = df.dropna()
            self._price_cache[symbol] = clean_df
            return clean_df
        except Exception as e:
            print(f"[-] Data Service connection failure for {symbol}: {e}")
            return pd.DataFrame()

    def clear_cache(self):
        self._price_cache.clear()
        self._nifty_cache = None