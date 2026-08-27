import pandas as pd
import numpy as np
import yfinance as yf
import os
import warnings

warnings.filterwarnings('ignore')

# --- Configuration ---
MIN_RS = 80                 # 🚀 Tightened from 70 to 80 for elite market leadership
MIN_INDUSTRY_RS = 70
MIN_MARKET_BREADTH = 45 
MIN_TURNOVER = 100000000     # ₹10 Crores (1e8) liquidity filter
LOOKBACK_PERIOD = "2y" 
MIN_DAYS_REQUIRED = 260
MIN_THEME_MEMBERS = 3  

# File Path Configuration
FOLDER_PATH = r"C:\Users\GS102\OneDrive\Research\Invest"
FILE_NAME = "NSE_EQ.csv"     # Automatically targets your uploaded file format
FILE_PATH = os.path.join(FOLDER_PATH, FILE_NAME)

# --- Global Cache ---
price_cache = {}
industry_map = {}
SYMBOLS_TO_SCAN = []

def clean_yfinance_df(df):
    """
    Guarantees that regardless of the yfinance version or MultiIndex layout,
    core columns are extracted as clean, uniform, unique 1D Series.
    """
    if df.empty:
        return df
        
    # Handle MultiIndex Columns safely
    if isinstance(df.columns, pd.MultiIndex):
        core_cols = ['Close', 'Open', 'High', 'Low', 'Volume']
        level_to_keep = 0
        for level in range(df.columns.nlevels):
            if any(c in core_cols for c in df.columns.get_level_values(level)):
                level_to_keep = level
                break
        df.columns = df.columns.get_level_values(level_to_keep)
        
    # Standardize column typography
    df.columns = [str(c).strip().capitalize() for c in df.columns]
    
    # Force structure down to 1D Series if duplicate layers exist
    for col_name in ['Close', 'Open', 'High', 'Low', 'Volume']:
        matched = [c for c in df.columns if c == col_name]
        if matched:
            series_data = df[matched[0]]
            if isinstance(series_data, pd.DataFrame):
                series_data = series_data.iloc[:, 0]
            df[col_name] = series_data
            
    return df

def load_universe_from_csv():
    global SYMBOLS_TO_SCAN, industry_map
    if not os.path.exists(FILE_PATH):
        raise FileNotFoundError(f"❌ Could not find the file at: {FILE_PATH}")
        
    print(f"📡 Loading universe from: {FILE_PATH}")
    df = pd.read_csv(FILE_PATH)
        
    # Clean and standardize column names
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    if "SYMBOL" not in df.columns:
        raise KeyError("❌ The CSV sheet must contain a column named 'SYMBOL'.")
        
    # Filter for standard Equity series if available
    if "SERIES" in df.columns:
        df = df[df["SERIES"] == "EQ"]
        
    # Look for any sector or theme groupings
    theme_col = None
    for col in ["THEME", "INDUSTRY", "SECTOR", "GROUP"]:
        if col in df.columns:
            theme_col = col
            break

    # Parse symbols and map them
    for _, row in df.iterrows():
        symbol = str(row["SYMBOL"]).strip().upper()
        if not symbol or symbol == "NAN" or len(symbol) < 2:
            continue
            
        yf_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        theme = str(row[theme_col]).strip() if theme_col else "GENERAL"
        if theme == "nan" or not theme:
            theme = "GENERAL"
            
        industry_map[yf_symbol] = theme
        SYMBOLS_TO_SCAN.append(yf_symbol)
        
    SYMBOLS_TO_SCAN = list(set(SYMBOLS_TO_SCAN))
    print(f"✅ Loaded {len(SYMBOLS_TO_SCAN)} unique symbols from CSV.")

def populate_cache(symbols):
    print(f"Fetching data for {len(symbols)} stocks...")
    failed_count = 0
    
    for count, sym in enumerate(symbols, 1):
        if count % 50 == 0:
            print(f"Cached {count}/{len(symbols)}...")
        try:
            df = yf.download(sym, period=LOOKBACK_PERIOD, auto_adjust=True, progress=False, threads=False)
            
            if df.empty:
                failed_count += 1
                continue
                
            # Process columns through the defensive cleaner
            df = clean_yfinance_df(df)
            
            # Active Trailing NaN Purging (Removes empty/partial market rows)
            df = df.dropna(subset=["Close"])
            
            if len(df) >= MIN_DAYS_REQUIRED:
                df.index = pd.to_datetime(df.index)
                price_cache[sym] = df
        except Exception as e:
            failed_count += 1
            if failed_count <= 5:
                print(f"⚠️ Error processing ticker {sym}: {e}")
            elif failed_count == 6:
                print("⚠️ Additional failure alerts suppressed to maintain clear console logs...")
                
    print(f"✅ Caching cycle finalized. Successfully stored: {len(price_cache)} tickers. Failed/Skipped: {failed_count}")

def calculate_market_breadth():
    above_50 = 0
    valid_stocks = 0
    
    for sym, df in price_cache.items():
        if len(df) >= 50:
            current = float(df["Close"].iloc[-1])
            ma50 = float(df["Close"].rolling(50).mean().iloc[-1])
            
            if current > ma50:
                above_50 += 1
            valid_stocks += 1
            
    print(f"\n📊 [BREADTH TELEMETRY] Stocks Above 50-DMA: {above_50} | Total Valid Checked: {valid_stocks}")
            
    if valid_stocks == 0: return 0
    return (above_50 / valid_stocks) * 100

def get_weighted_return(close_series):
    try:
        ret20 = close_series.iloc[-1] / close_series.iloc[-20]
        ret60 = close_series.iloc[-1] / close_series.iloc[-60]
        ret120 = close_series.iloc[-1] / close_series.iloc[-120]
        ret250 = close_series.iloc[-1] / close_series.iloc[-250]
        return (ret20 * 0.4) + (ret60 * 0.3) + (ret120 * 0.2) + (ret250 * 0.1)
    except:
        return 1

def build_cross_sectional_rs(symbols, industry_map, nifty_weighted_ret):
    raw_stock_rs = {}
    theme_groups = {}
    
    for s in symbols:
        if s in price_cache:
            df = price_cache[s]
            stock_wr = get_weighted_return(df["Close"])
            raw_stock_rs[s] = stock_wr / nifty_weighted_ret
            
            theme = industry_map.get(s, "GENERAL")
            theme_groups.setdefault(theme, []).append(s)

    stock_rs_percentiles = {}
    if raw_stock_rs:
        stock_rs_percentiles = (pd.Series(raw_stock_rs).rank(pct=True).mul(100).astype(int).clip(1, 99).to_dict())

    raw_theme_rs = {}
    for theme, members in theme_groups.items():
        if len(members) < MIN_THEME_MEMBERS and theme != "GENERAL": continue
            
        returns, weights = [], []
        for stock in members:
            if stock not in price_cache: continue
            df = price_cache[stock]
            
            ret = get_weighted_return(df["Close"])
            avg_vol = df["Volume"].iloc[-20:].mean()
            liquidity_weight = np.sqrt(avg_vol * df["Close"].iloc[-1])
            
            returns.append(ret)
            weights.append(liquidity_weight)

        if returns:
            theme_return = np.average(returns, weights=weights)
            raw_theme_rs[theme] = theme_return / nifty_weighted_ret

    theme_rs_percentiles = {}
    if raw_theme_rs:
        theme_rs_percentiles = (pd.Series(raw_theme_rs).rank(pct=True).mul(100).astype(int).clip(1, 99).to_dict())
        
    intra_theme_ranks = {}
    for theme, members in theme_groups.items():
        sorted_members = sorted(members, key=lambda x: stock_rs_percentiles.get(x, 0), reverse=True)
        for rank, sym in enumerate(sorted_members, 1):
            intra_theme_ranks[sym] = rank

    return stock_rs_percentiles, theme_rs_percentiles, intra_theme_ranks

def check_minervini_trend(df):
    close = df["Close"]
    current = float(close.iloc[-1])
    
    ma200_series = close.rolling(200).mean()
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma150 = float(close.rolling(150).mean().iloc[-1])
    ma200 = float(ma200_series.iloc[-1])
    ma200_20d_ago = float(ma200_series.iloc[-20])
    
    high_52w = float(close.tail(250).max())
    low_52w = float(close.tail(250).min())

    if not (current > ma50 > ma150 > ma200): return False
    if ma200 <= ma200_20d_ago: return False 
    if current < (high_52w * 0.75): return False
    if current < (low_52w * 1.25): return False
    
    return True

def check_weekly_alignment(df):
    try:
        weekly = df.resample('W-FRI').agg({'Close': 'last'}).dropna()
        if len(weekly) < 40: return False
            
        ma10 = float(weekly['Close'].rolling(10).mean().iloc[-1])
        ma40 = float(weekly['Close'].rolling(40).mean().iloc[-1])
        return ma10 > ma40
    except:
        return False

def measure_vcp_contractions(df, lookback=150):
    recent = df.tail(lookback)
    if len(recent) < 50: return [], []

    highs, lows, vols = recent["High"], recent["Low"], recent["Volume"]
    contractions, vol_contractions = [], []

    peak1_idx = highs.idxmax()
    if peak1_idx == highs.index[-1]: return [], [] 
    low1_idx = lows.loc[peak1_idx:].idxmin()
    contractions.append(((highs[peak1_idx] - lows[low1_idx]) / highs[peak1_idx]) * 100)
    vol_contractions.append(vols.loc[peak1_idx:low1_idx].mean())

    if low1_idx == lows.index[-1]: return contractions, vol_contractions
    peak2_idx = highs.loc[low1_idx:].idxmax()
    if peak2_idx == highs.index[-1]: return contractions, vol_contractions
    low2_idx = lows.loc[peak2_idx:].idxmin()
    contractions.append(((highs[peak2_idx] - lows[low2_idx]) / highs[peak2_idx]) * 100)
    vol_contractions.append(vols.loc[peak2_idx:low2_idx].mean())

    if low2_idx == lows.index[-1]: return contractions, vol_contractions
    peak3_idx = highs.loc[low2_idx:].idxmax()
    if peak3_idx == highs.index[-1]: return contractions, vol_contractions
    low3_idx = lows.loc[peak3_idx:].idxmin()
    contractions.append(((highs[peak3_idx] - lows[low3_idx]) / highs[peak3_idx]) * 100)
    vol_contractions.append(vols.loc[peak3_idx:low3_idx].mean())

    return [round(c, 1) for c in contractions if c > 1.0], vol_contractions

def calculate_base_depth(df):
    high_120 = df["High"].tail(120).max()
    low_120 = df["Low"].tail(120).min()
    return round(((high_120 - low_120) / low_120) * 100, 2)

def calculate_vcp_score(df):
    contractions, vol_contractions = measure_vcp_contractions(df)
    score = 0
    
    if len(contractions) >= 2 and contractions[1] < contractions[0]: score += 3
    if len(contractions) >= 3 and contractions[2] < contractions[1]: score += 4
        
    if len(vol_contractions) >= 3:
        if vol_contractions[2] < vol_contractions[1] < vol_contractions[0]: score += 3
    elif len(vol_contractions) == 2:
        if vol_contractions[1] < vol_contractions[0]: score += 2

    overall_depth = calculate_base_depth(df)
    if overall_depth <= 8: score += 3
    elif overall_depth <= 15: score += 2

    return score, contractions

def volume_metrics(df):
    recent = df["Volume"].tail(10).mean()
    prior = df["Volume"].tail(50).head(40).mean()
    dryup_ratio = recent / prior

    score = 0
    if dryup_ratio <= 0.50: score += 4
    elif dryup_ratio <= 0.70: score += 3
    elif dryup_ratio <= 0.85: score += 2
    
    rvol = df["Volume"].iloc[-1] / df["Volume"].tail(20).mean()
    if rvol < 0.8:
        score += 2  

    return score, round(rvol, 2), round(dryup_ratio * 100, 1)

def check_21ema_tightness(df):
    close = df["Close"]
    current_price = float(close.iloc[-1])
    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    distance = (abs(current_price - ema21) / ema21) * 100
    return 2 if distance < 3.0 else 0, round(distance, 1)

def interpret_vcp(contractions, breakout_distance, rvol):
    """
    Converts raw VCP contractions into simple analyst commentary.
    """
    if len(contractions) < 2:
        return (
            "Incomplete",
            "Not enough contraction waves detected to qualify as a mature VCP."
        )

    c1 = contractions[0]
    c2 = contractions[1]
    c3 = contractions[2] if len(contractions) >= 3 else None

    if len(contractions) >= 3:
        # Elite textbook VCP
        if c1 > c2 > c3 and c3 <= 4:
            verdict = "A+ Elite VCP"
            comment = (
                "Closest to a textbook Minervini VCP. "
                "Each contraction is smaller than the previous one and "
                "the final contraction is exceptionally tight."
            )
        # Near ideal
        elif c1 > c2 > c3 and c3 <= 5:
            verdict = "A Near-Ideal"
            comment = (
                "Actually one of the best setups in the scan. "
                "The final contraction sits in the sweet spot where explosive breakouts often emerge."
            )
        # Good but stalled
        elif c1 > c2 and abs(c3 - c2) <= 1:
            verdict = "B+ High Quality"
            comment = (
                "Very good but not perfect. "
                "The last contraction did not tighten further."
            )
        # Volatility expanding
        elif c3 > c2:
            verdict = "C Warning"
            comment = (
                "The final contraction expanded instead of shrinking. "
                "The stock may require additional consolidation."
            )
        else:
            verdict = "B Constructive"
            comment = (
                "Constructive VCP structure with acceptable contraction behaviour."
            )
    elif c1 > c2:
        verdict = "B Developing"
        comment = (
            "Constructive VCP structure. "
            "A third tighter contraction would improve setup quality."
        )
    else:
        verdict = "C Loose Base"
        comment = (
            "Volatility is not contracting consistently."
        )

    # Context Enhancements
    if breakout_distance <= 2:
        comment += " Stock is sitting very close to its breakout trigger."
    if rvol >= 2:
        comment += " Relative volume confirms active participation."

    return verdict, comment

def analyze_stock(symbol, industry_map, stock_rs, theme_rs, intra_theme):
    df = price_cache.get(symbol)
    if df is None or len(df) < MIN_DAYS_REQUIRED: return None
        
    close = df["Close"]
    current_price = float(close.iloc[-1])
    
    # 1. Liquidity Filter (Avg Turnover > ₹10 Cr)
    avg_turnover = df["Volume"].tail(20).mean() * close.tail(20).mean()
    if avg_turnover < MIN_TURNOVER: return None
    
    rs_rating = stock_rs.get(symbol, 1)
    industry = industry_map.get(symbol, "GENERAL")
    industry_rs = theme_rs.get(industry, 1)
    group_rank = intra_theme.get(symbol, 99)

    # 2. Hard Structural & Trend Filters
    if rs_rating < MIN_RS: return None
    
    # Dynamic Industry Bypass if no Theme column is found in CSV
    if industry != "GENERAL" and industry_rs < MIN_INDUSTRY_RS: return None 
    if not check_minervini_trend(df): return None
    if not check_weekly_alignment(df): return None

    # 3. Distance & Pivot Filters
    high_52w = float(close.tail(250).max())
    from_high = ((current_price - high_52w) / high_52w) * 100
    if from_high < -20: return None

    pivot = float(df["High"].shift(1).tail(30).max())
    breakout_distance = ((pivot - current_price) / current_price) * 100
    if breakout_distance > 15: return None

    # 4. Base Building Math
    vcp_score, contractions = calculate_vcp_score(df)
    vol_score, rvol, dryup_pct = volume_metrics(df)
    ema_score, ema_dist = check_21ema_tightness(df)
    
    verdict, comment = interpret_vcp(
        contractions,
        breakout_distance,
        rvol
    )
    
    # 5. Breakout Volume Trap Filter (Optimized Optimization Rule)
    # 🚀 Loosened up to catch elite quiet consolidations building immediately below the key trigger level
    if breakout_distance <= 0.5 and rvol < 1.2:
        return None 
    
    # 6. Synthesize Base Score + Top-Down Multipliers
    score = vcp_score + vol_score + ema_score
    
    if industry != "GENERAL":
        if industry_rs >= 95: score += 5
        elif industry_rs >= 90: score += 4
        elif industry_rs >= 80: score += 3
        elif industry_rs >= 70: score += 2

    if rs_rating >= 90 and industry_rs >= 90 and industry != "GENERAL":
        score += 3

    vcp_string = ">".join(map(lambda x: str(int(x)), contractions)) if contractions else "N/A"

    return {
        "Symbol": symbol.replace(".NS", ""),
        "Ind": industry,
        "Ind RS": industry_rs if industry != "GENERAL" else "N/A",
        "Stk RS": rs_rating,
        "Rank": f"#{group_rank}" if industry != "GENERAL" else f"#{group_rank}/{len(price_cache)}",
        "Score": score,
        "VCP Flow": vcp_string,
        "Pivot %": round(breakout_distance, 1),
        "21EMA %": ema_dist, 
        "Dryup %": dryup_pct,
        "RVOL": rvol,
        "Verdict": verdict,
        "Comment": comment
    }

def main():
    load_universe_from_csv()
    
    if not SYMBOLS_TO_SCAN:
        print("❌ No valid symbols parsed. Aborting scan.")
        return

    print("Fetching NIFTY baseline data...")
    nifty_df = yf.download("^NSEI", period=LOOKBACK_PERIOD, auto_adjust=True, progress=False, threads=False)
    nifty_df = clean_yfinance_df(nifty_df).dropna(subset=["Close"])
    
    if len(nifty_df) < MIN_DAYS_REQUIRED:
        print("Error: Not enough NIFTY data retrieved.")
        return
        
    nifty_weighted_ret = get_weighted_return(nifty_df["Close"])
    populate_cache(SYMBOLS_TO_SCAN)
    
    print("\nEvaluating Global Market Breadth...")
    breadth_pct = calculate_market_breadth()
    print(f"Breadth (>50SMA): {breadth_pct:.1f}%")
    
    if breadth_pct < MIN_MARKET_BREADTH:
        print(f"\n🛑 HARD STOP: Market Breadth is {breadth_pct:.1f}%. Below safe threshold of {MIN_MARKET_BREADTH}%.")
        print("Capital preservation mode. Most breakout setups will fail in this environment. Scan aborted.")
        return
    
    print("\nCalculating Cross-Sectional RS Percentiles & Group Ranks...")
    stock_rs, theme_rs, intra_theme = build_cross_sectional_rs(SYMBOLS_TO_SCAN, industry_map, nifty_weighted_ret)
    
    # Notice module for the generic CSV layout
    if all(theme == "GENERAL" for theme in industry_map.values()):
        print("\n💡 NOTICE: No 'THEME' or 'INDUSTRY' column was found in your NSE_EQ.csv file.")
        print("   All stocks have been safely mapped to 'GENERAL'. Industry RS filters have been automatically bypassed.")
        print("   Sorting will rank candidates purely by individual Stock RS performance.")
    
    print("\nScanning for High-Quality VCP Bases...")
    results = []
    
    for sym in price_cache.keys():
        res = analyze_stock(sym, industry_map, stock_rs, theme_rs, intra_theme)
        if res:
            results.append(res)

    if results:
        df_results = pd.DataFrame(results)
        
        # 1. Reorder columns to group Verdict and Comment
        cols = ["Symbol", "Ind", "Stk RS", "Rank", "Score", "VCP Flow", "Pivot %", "Verdict", "Comment"]
        # Add back any other columns you want to keep
        df_results = df_results[cols]
        
        # 2. Sort
        sort_cols = ["Stk RS", "Score"]
        df_results = df_results.sort_values(by=sort_cols, ascending=[False, False])
        
        # 3. Optimized Display Formatting
        pd.set_option('display.max_colwidth', 40) # Keeps comments readable but compact
        pd.set_option('display.width', 150)       # Adjust based on your terminal size
        
        print("\n=== BASE BUILDING SCANNER: PRIME INSTITUTIONAL SETUPS ===")
        print(df_results.to_string(index=False))
    else:
        print("\nNo stocks met the rigorous base building criteria today.")

if __name__ == "__main__":
    main()