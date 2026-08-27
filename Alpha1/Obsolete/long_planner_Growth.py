import pandas as pd
import numpy as np
import yfinance as yf
import datetime

# =========================
# CONFIG (₹15K SIP CORE)
# =========================
BASE_CAPITAL = 15000
TRADE_FILE = "compounder_v9_portfolio.xlsx"

# =========================
# UNIVERSE
# =========================
WATCHLIST = [
    "TCS", "INFY", "HCLTECH", "PERSISTENT", "COFORGE", "KPITTECH", "TATAELXSI",
    "RELIANCE", "LT", "M&M",
    "TITAN", "MARUTI",
    "NAVINFLUOR", "DEEPAKNTR",
    "360ONE", "AARTIIND"
]

# =========================
# SECTOR MAP (CRITICAL)
# =========================
SECTOR_MAP = {
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT",
    "PERSISTENT": "IT", "COFORGE": "IT", "KPITTECH": "IT", "TATAELXSI": "IT",

    "RELIANCE": "ENERGY",
    "LT": "INFRA",
    "M&M": "AUTO",
    "TITAN": "CONSUMER",
    "MARUTI": "AUTO",

    "NAVINFLUOR": "CHEMICAL",
    "DEEPAKNTR": "CHEMICAL",
    "AARTIIND": "CHEMICAL",

    "360ONE": "FINANCE"
}

# =========================
# DATA FETCH
# =========================
def get_data(symbol):
    try:
        t = yf.Ticker(symbol + ".NS")
        hist = t.history(period="1y")
        info = {}

        try:
            info = t.info
        except:
            pass

        if hist.empty or len(hist) < 120:
            return None, None

        return hist, info

    except:
        return None, None


# =========================
# FEATURE ENGINE
# =========================
def extract_features(symbol):
    hist, info = get_data(symbol)
    if hist is None:
        return None

    close = hist["Close"]

    returns = close.pct_change().mean() * 252
    volatility = close.pct_change().std() * np.sqrt(252)
    momentum = close.pct_change(63).iloc[-1] if len(close) > 63 else 0

    ma200 = close.rolling(200).mean().iloc[-1]
    trend = 1 if close.iloc[-1] > ma200 else 0

    drawdown = (close / close.cummax() - 1).min()

    roe = info.get("returnOnEquity", 0)
    rev_growth = info.get("revenueGrowth", 0)

    return {
        "returns": returns,
        "volatility": volatility,
        "momentum": momentum,
        "trend": trend,
        "drawdown": drawdown,
        "roe": roe if roe else 0,
        "revenue_growth": rev_growth if rev_growth else 0
    }


# =========================
# Z-SCORE NORMALIZATION
# =========================
def zscore(series):
    arr = np.array(series)
    if np.std(arr) == 0:
        return np.zeros(len(arr))
    return (arr - np.mean(arr)) / (np.std(arr) + 1e-9)


# =========================
# SCORE ENGINE (INSTITUTIONAL)
# =========================
def compute_scores(universe):
    raw_data = {}

    for s in universe:
        f = extract_features(s)
        if f:
            raw_data[s] = f

    df = pd.DataFrame(raw_data).T

    # Z-score normalization (CRITICAL v9 upgrade)
    df["growth_z"] = zscore(df["returns"])
    df["momentum_z"] = zscore(df["momentum"])
    df["volatility_z"] = zscore(df["volatility"])
    df["roe_z"] = zscore(df["roe"])
    df["revenue_z"] = zscore(df["revenue_growth"])

    # Composite Score (institutional weighting)
    df["score"] = (
        df["growth_z"] * 2.0 +
        df["momentum_z"] * 1.8 +
        df["roe_z"] * 1.5 +
        df["revenue_z"] * 1.5 -
        df["volatility_z"] * 1.2
    )

    return df["score"].sort_values(ascending=False)


# =========================
# PORTFOLIO CONSTRUCTION (SECTOR CONTROL)
# =========================
def build_portfolio(scores):

    ranked = scores.items()

    selected = []
    sector_count = {}

    for stock, score in ranked:
        sector = SECTOR_MAP.get(stock, "OTHER")

        # sector cap = 1 stock per sector (core rule)
        if sector_count.get(sector, 0) >= 1:
            continue

        selected.append((stock, score))
        sector_count[sector] = sector_count.get(sector, 0) + 1

    # allocate capital
    total_score = sum([abs(s[1]) + 1 for s in selected])

    portfolio = []
    remaining_cash = BASE_CAPITAL

    for stock, score in selected:

        price = yf.Ticker(stock + ".NS").history(period="1d")["Close"].iloc[-1]

        weight = (abs(score) + 1) / total_score
        allocation = BASE_CAPITAL * weight

        shares = int(allocation // price)
        invested = shares * price
        remaining_cash -= invested

        portfolio.append({
            "Stock": stock,
            "Score": round(score, 2),
            "Allocation": round(allocation, 2),
            "Shares": shares,
            "Invested": round(invested, 2),
            "Sector": SECTOR_MAP.get(stock, "OTHER")
        })

    return pd.DataFrame(portfolio), remaining_cash


# =========================
# EXECUTION ENGINE
# =========================
def run():

    print("\n🧠 COMPOUNDER v9 PORTFOLIO BRAIN")
    print("=" * 60)

    scores = compute_scores(WATCHLIST)
    portfolio, cash = build_portfolio(scores)

    print(portfolio)
    print("\n💵 Remaining Cash:", round(cash, 2))

    portfolio.to_excel(TRADE_FILE, index=False)
    print("\n✔ Saved → compounder_v9_portfolio.xlsx")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    run()