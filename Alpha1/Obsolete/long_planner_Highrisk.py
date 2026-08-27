import pandas as pd
import numpy as np
import yfinance as yf
import datetime

# =========================
# CONFIG
# =========================
CORE_CAPITAL = 15000
HIGH_RISK_CAPITAL = 10000

TRADE_FILE = "compounder_v9_plus_risk.xlsx"

# =========================
# CORE COMPOUNDERS (QUALITY)
# =========================
CORE_UNIVERSE = [
    "TCS", "INFY", "HCLTECH", "PERSISTENT", "COFORGE", "KPITTECH", "TATAELXSI",
    "RELIANCE", "LT", "M&M",
    "TITAN", "MARUTI",
    "NAVINFLUOR", "DEEPAKNTR",
    "360ONE", "AARTIIND"
]

# =========================
# HIGH RISK BETS (ASYMMETRIC)
# =========================
HIGH_RISK_UNIVERSE = [
    "AVALON", "PGEL", "SYRMA", "AMBER",
    "SAGHAELECT", "DCXINDIA", "JSWINFRA",
    "ALLCARGO", "IRCON", "GATEWAY",
    "RELCHEMOT", "COCHINSHIP", "PARAS",
    "ASTRAMICRO", "BORORENEW", "INOXWIND",
    "SUZLON", "ANGELONE", "MOTILALOFS",
    "POLICYBZR", "FIVESTAR", "HAPPSTMNDS",
    "TATAELXSI", "BLACKBOX"
]

# =========================
# FEATURE ENGINE
# =========================
def get_features(symbol):
    try:
        t = yf.Ticker(symbol + ".NS")
        hist = t.history(period="1y")
        if hist.empty or len(hist) < 120:
            return None

        close = hist["Close"]

        returns = close.pct_change().mean() * 252
        volatility = close.pct_change().std() * np.sqrt(252)
        momentum = close.pct_change(63).iloc[-1] if len(close) > 63 else 0

        ma200 = close.rolling(200).mean().iloc[-1]
        trend = 1 if close.iloc[-1] > ma200 else 0

        drawdown = (close / close.cummax() - 1).min()

        info = {}
        try:
            info = t.info
        except:
            pass

        roe = info.get("returnOnEquity", 0) or 0
        rev = info.get("revenueGrowth", 0) or 0

        return {
            "returns": returns,
            "volatility": volatility,
            "momentum": momentum,
            "trend": trend,
            "drawdown": drawdown,
            "roe": roe,
            "revenue": rev
        }

    except:
        return None


# =========================
# SCORE ENGINE (CORE)
# =========================
def score_core(symbol):
    f = get_features(symbol)
    if not f:
        return None

    score = (
        f["returns"] * 2.0 +
        f["momentum"] * 1.5 +
        f["roe"] * 1.2 +
        f["revenue"] * 1.0 +
        f["trend"] * 0.5
    ) / (f["volatility"] + 0.2)

    return score


# =========================
# SCORE ENGINE (HIGH RISK)
# =========================
def score_high_risk(symbol):
    f = get_features(symbol)
    if not f:
        return None

    # higher weight to momentum + trend (growth chasing)
    score = (
        f["momentum"] * 2.5 +
        f["returns"] * 1.5 +
        f["trend"] * 1.5 -
        f["drawdown"] * 2.0
    ) / (f["volatility"] + 0.25)

    return score


# =========================
# PORTFOLIO BUILDER
# =========================
def build_portfolio(universe, scorer, capital):

    scored = {}

    for s in universe:
        sc = scorer(s)
        if sc is not None:
            scored[s] = sc

    ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)

    total_score = sum([abs(s[1]) + 1 for s in ranked])

    rows = []
    remaining = capital

    for stock, score in ranked:

        try:
            price = yf.Ticker(stock + ".NS").history(period="1d")["Close"].iloc[-1]
        except:
            continue

        weight = (abs(score) + 1) / total_score
        allocation = capital * weight

        shares = int(allocation // price)
        invested = shares * price
        remaining -= invested

        rows.append({
            "Stock": stock,
            "Score": round(score, 2),
            "Allocation": round(allocation, 2),
            "Shares": shares,
            "Invested": round(invested, 2),
        })

    return pd.DataFrame(rows), remaining


# =========================
# EXECUTION ENGINE
# =========================
def run():

    print("\n🧠 COMPOUNDER v9 + HIGH RISK ENGINE")
    print("=" * 60)

    core_portfolio, core_cash = build_portfolio(
        CORE_UNIVERSE,
        score_core,
        CORE_CAPITAL
    )

    risk_portfolio, risk_cash = build_portfolio(
        HIGH_RISK_UNIVERSE,
        score_high_risk,
        HIGH_RISK_CAPITAL
    )

    print("\n🟢 CORE COMPOUNDERS")
    print(core_portfolio)

    print("\n🔴 HIGH RISK BETS")
    print(risk_portfolio)

    print("\n💵 Remaining Core Cash:", round(core_cash, 2))
    print("💵 Remaining Risk Cash:", round(risk_cash, 2))

    with pd.ExcelWriter(TRADE_FILE) as writer:
        core_portfolio.to_excel(writer, sheet_name="CORE", index=False)
        risk_portfolio.to_excel(writer, sheet_name="HIGH_RISK", index=False)

    print("\n✔ Saved → compounder_v9_plus_risk.xlsx")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    run()