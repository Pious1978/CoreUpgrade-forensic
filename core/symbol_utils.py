"""
core/symbol_utils.py

#59 - Ticker alias/common-name-variant handling, #60 - NSE-then-BSE
fallback for live fundamentals fetches.

Both confirmed as real, recurring needs found independently across two
of the user's own past scripts (Alpha1/Obsolete/Tracking_trade Tool.py
and Alpha1/Obsolete/momentum.py) - not one-off ideas.

Scope, precisely: this only matters for LIVE fundamentals fetches
(yfinance .info calls in Stock_Lookup.py and Compounder_Scanner.py).
Everything else in this system reads from parquet_cache (already-
downloaded historical data, keyed by whatever ticker name was used at
backfill time), so this fix is deliberately narrow rather than a
system-wide symbol-resolution overhaul.
"""

import yfinance as yf

# Real, confirmed name changes and common variants - found directly in
# the user's own past scripts, not guessed. Extend this list as more
# are found; it's deliberately small and evidence-based rather than an
# attempt at a comprehensive market-wide mapping.
TICKER_ALIASES = {
    "RIL": "RELIANCE",
    "PBFINTECH": "POLICYBZR",
    "HINDCOOPER": "HINDCOPPER",  # common typo, confirmed in past script
}

# Stocks confirmed to be BSE-only (no NSE listing) - found directly in
# the user's own past scripts.
BSE_ONLY_TICKERS = {"ECORECO", "DECCANCE", "DECNGOLD"}


def normalize_ticker(ticker):
    """Applies known alias corrections - returns the ticker unchanged
    if it's not a known alias."""

    clean = ticker.upper().strip()
    return TICKER_ALIASES.get(clean, clean)


def fetch_yfinance_info(ticker, timeout_executor=None):
    """
    Real NSE-then-BSE fallback, confirmed as a genuine pattern in the
    user's own past scripts. Tries .NS first (the vast majority of
    stocks); if that returns empty/invalid info, falls back to .BO
    before giving up. Alias normalization is applied first, since a
    renamed ticker needs correcting before either suffix will resolve.

    Returns the yfinance .info dict, or None if neither exchange has
    real data for this ticker.
    """

    normalized = normalize_ticker(ticker)

    for suffix in [".NS", ".BO"]:
        try:
            info = yf.Ticker(f"{normalized}{suffix}").info

            # A genuinely valid response has real fields; yfinance
            # sometimes returns a near-empty dict for an invalid
            # ticker rather than raising an exception, so an empty or
            # near-empty dict is NOT treated as success.
            if info and len(info) > 5:
                return info

        except Exception:
            continue

    return None