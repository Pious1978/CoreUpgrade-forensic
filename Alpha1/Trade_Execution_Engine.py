import yfinance as yf
import pandas as pd
import numpy as np

# ============================================================
# DATA FETCH
# ============================================================

def fetch_stock_data(symbol):

    possible = [symbol + ".NS", symbol + ".BO", symbol]

    for sym in possible:
        try:
            df = yf.download(
                sym,
                period="1y",
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=False
            )

            if df.empty or len(df) < 200:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

            print(f"✅ Using: {sym}")
            return df, sym

        except:
            continue

    return None, None


# ============================================================
# INDICATORS
# ============================================================

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(period).mean()


def get_ema(df):
    close = df["Close"]
    return (
        close,
        close.ewm(span=20).mean(),
        close.ewm(span=50).mean(),
        close.ewm(span=200).mean()
    )


# ============================================================
# SETUP CLASSIFICATION
# ============================================================

def classify_setup(df, ema20, ema50):

    close = df["Close"]
    curr = close.iloc[-1]
    high20 = df["High"].tail(20).max()

    if curr > high20:
        return "EARLY_BREAKOUT"

    if curr >= high20 * 0.98:
        return "BREAKOUT_READY"

    if ema20.iloc[-1] > ema50.iloc[-1] and curr < ema20.iloc[-1]:
        return "PULLBACK_ENTRY"

    return "EXTENDED"


# ============================================================
# CONFIRMATION ENGINE
# ============================================================

def confirmations(df, ema20, ema50, rsi_val, rvol):

    curr = df["Close"].iloc[-1]

    score = 0

    if curr > ema20.iloc[-1]:
        score += 1

    if curr > ema50.iloc[-1]:
        score += 1

    if rsi_val > 50:
        score += 1

    if rvol > 1:
        score += 1

    return score


# ============================================================
# POSITION SIZING (VOLATILITY ADJUSTED)
# ============================================================

def position_size(entry, sl, account_size, risk_pct, atr_val):

    risk_amt = account_size * risk_pct
    risk_per_share = abs(entry - sl)

    if risk_per_share <= 0:
        return 0

    atr_pct = atr_val / entry

    if atr_pct > 0.05:
        size_factor = 0.75
    elif atr_pct < 0.02:
        size_factor = 1.25
    else:
        size_factor = 1.0

    return int((risk_amt * size_factor) / risk_per_share)


# ============================================================
# TRADE LEVELS
# ============================================================

def trade_levels(entry, atr_val):

    sl = entry - (2 * atr_val)

    t1 = entry + (2 * atr_val)
    t2 = entry + (4 * atr_val)
    t3 = entry + (8 * atr_val)

    return sl, t1, t2, t3


# ============================================================
# EXECUTION DECISION
# ============================================================

def decision_logic(conf_score, setup, rr):

    if conf_score >= 4 and rr >= 2:
        return "BUY NOW"

    elif conf_score >= 2:
        return "WAIT FOR TRIGGER"

    else:
        return "SKIP"


# ============================================================
# MAIN ENGINE
# ============================================================

def run_engine():

    print("\n" + "="*60)
    print("🚀 TRADE EXECUTION ENGINE v9 (EXECUTION LAYER)")
    print("="*60)

    ticker = input("Enter Stock: ").upper().strip()

    account_size = float(input("Enter Account Size: "))
    risk_pct = float(input("Enter Risk % (e.g. 0.01 = 1%): "))

    df, sym = fetch_stock_data(ticker)

    if df is None:
        print("❌ No data found")
        return

    close, ema20, ema50, ema200 = get_ema(df)

    rsi_val = rsi(close).iloc[-1]

    atr_val = atr(df).iloc[-1]

    volume = df["Volume"]
    rvol = volume.iloc[-1] / volume.tail(20).mean()

    setup = classify_setup(df, ema20, ema50)

    entry = ema20.iloc[-1] if setup != "EARLY_BREAKOUT" else df["High"].tail(10).max()

    sl, t1, t2, t3 = trade_levels(entry, atr_val)

    rr = (t1 - entry) / (entry - sl) if entry > sl else 0

    conf_score = confirmations(df, ema20, ema50, rsi_val, rvol)

    qty = position_size(entry, sl, account_size, risk_pct, atr_val)

    signal = decision_logic(conf_score, setup, rr)

    # ========================================================
    # OUTPUT
    # ========================================================

    print("\n" + "="*60)
    print(f"📊 {sym} | Price: {df['Close'].iloc[-1]:.2f}")
    print("="*60)

    print(f"🧠 Setup: {setup}")
    print(f"📈 RSI: {rsi_val:.2f}")
    print(f"📦 RVOL: {rvol:.2f}")
    print(f"⚖️ RR: {rr:.2f}")
    print(f"🔢 Confirmation Score: {conf_score}/4")

    print("\n🎯 TRADE PLAN")
    print(f"Entry: {entry:.2f}")
    print(f"Stop:  {sl:.2f}")
    print(f"T1:    {t1:.2f}")
    print(f"T2:    {t2:.2f}")
    print(f"T3:    {t3:.2f}")

    print("\n📦 POSITION")
    print(f"Qty: {qty}")

    print("\n🚦 SIGNAL:", signal)

    print("="*60)


if __name__ == "__main__":
    run_engine()