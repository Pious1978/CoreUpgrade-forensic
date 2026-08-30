import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# =========================
# CONFIG
# =========================
MANUAL_SYMBOLS = {
    "AVALONTECH": "AVALONTECH.BO",
    "PBFINTECH": "POLICYBZR.NS",
    "BLACKBOX": None   # disabled (invalid Yahoo ticker)
}

BLACKLIST = {"AVALONTECH"}

WATCHLIST = [
    "PGEL","SYRMA","AMBER","DCXINDIA","JSWINFRA",
    "ALLCARGO","IRCON","GMDCLTD","COCHINSHIP",
    "PARAS","ASTRAMICRO","BORORENEW","INOXWIND",
    "SUZLON","ANGELONE","MOTILALOFS","PBFINTECH",
    "5PAISA","HAPPSTMNDS","TATAELXSI","BLACKBOX"
]

# =========================
# UTILITIES
# =========================
def clean_df(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def safe_float(x):
    if isinstance(x, pd.Series):
        x = x.iloc[-1]
    return float(x)

# =========================
# FETCH DATA
# =========================
def fetch_data(symbol):

    if symbol in BLACKLIST:
        return None, None

    if MANUAL_SYMBOLS.get(symbol) is None:
        return None, None

    symbols = []

    if symbol in MANUAL_SYMBOLS:
        symbols = [MANUAL_SYMBOLS[symbol]]
    else:
        symbols = [symbol + ".NS", symbol + ".BO"]

    for sym in symbols:
        try:
            df = yf.download(sym, period="1y", interval="1d", progress=False)
            df = clean_df(df)

            if df is None or len(df) < 100:
                continue

            return df, sym

        except:
            continue

    return None, None

# =========================
# NIFTY RETURN
# =========================
def get_nifty_return():

    df = yf.download("^NSEI", period="1y", interval="1d", progress=False)
    df = clean_df(df)

    if df is None or len(df) < 50:
        return 0.0

    lookback = min(126, len(df) - 1)

    curr = safe_float(df["Close"].iloc[-1])
    past = safe_float(df["Close"].iloc[-lookback])

    return (curr / past) - 1

# =========================
# ANALYSIS ENGINE
# =========================
def analyze_stock(symbol, nifty_return):

    df, used = fetch_data(symbol)
    if df is None:
        return None

    # Indicators
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["Vol_Avg"] = df["Volume"].rolling(20).mean()

    curr = safe_float(df["Close"].iloc[-1])
    sma20 = safe_float(df["SMA20"].iloc[-1])
    sma50 = safe_float(df["SMA50"].iloc[-1])
    vol = safe_float(df["Volume"].iloc[-1])
    vol_avg = safe_float(df["Vol_Avg"].iloc[-1])

    if np.isnan(curr) or np.isnan(sma20) or np.isnan(sma50):
        return None

    if vol_avg == 0 or np.isnan(vol_avg):
        return None

    # Trend
    trend = (curr > sma20) and (sma20 > sma50)

    # Breakout
    breakout_level = float(df["High"].tail(20).max())
    breakout = curr >= breakout_level * 0.995

    # Volume
    vol_ratio = vol / vol_avg

    # RS
    lookback = min(126, len(df) - 1)
    past_price = safe_float(df["Close"].iloc[-lookback])
    rs = ((curr / past_price) - 1) - float(nifty_return)

    # Signals
    strong = breakout and vol_ratio > 1.5 and rs > 0
    mid = breakout and rs > 0
    early = trend and rs > 0

    if not (strong or mid or early):
        return None

    entry = round(curr, 2)
    stop = round(df["Low"].tail(5).min(), 2)

    if entry <= stop:
        return None

    target = round(entry + (entry - stop) * 2, 2)
    rr = round((target - entry) / (entry - stop), 2)

    return {
        "Stock": used,
        "Price": entry,
        "Stop": stop,
        "Target": target,
        "R:R": rr,
        "Signal": "STRONG" if strong else "MID" if mid else "EARLY"
    }

# =========================
# MAIN
# =========================
def run_momentum_scanner():

    print("\n🚀 Running Momentum Scanner...\n")

    nifty_return = get_nifty_return()
    results = []

    for stock in WATCHLIST:
        res = analyze_stock(stock, nifty_return)
        if res:
            results.append(res)

    if not results:
        print("❌ No setups found.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values(by="R:R", ascending=False)

    print(df.to_string(index=False))

    file = f"scan_{datetime.now().strftime('%Y%m%d')}.xlsx"
    df.to_excel(file, index=False)

    print(f"\n📁 Saved: {file}")

# =========================
if __name__ == "__main__":
    run_momentum_scanner()