# =============================================================================
# 📊 ALPHA V14: ROLLING EVENT-INTEGRATED INSTITUTIONAL MATRIX
# Phase Segmentation + Shortlist Adaptive Fallback Protection Protocol
# =============================================================================

import os
import time
import warnings
import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# =============================================================================
# SYSTEM CONFIGURATION
# =============================================================================
BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest"
CSV_PATH = os.path.join(BASE_DIR, "nse_eq.csv")
SHORTLIST_INPUT_PATH = os.path.join(BASE_DIR, "FUNDAMENTAL_SHORTLIST.xlsx")
EXTERNAL_FUNDAMENTALS_FILE = os.path.join(BASE_DIR, "screener_data.csv")
OUTPUT_EXCEL_FILE = os.path.join(BASE_DIR, "ALPHA_V14_QUANT_MATRIX.xlsx")

MIN_PRICE = 50
MIN_TURNOVER_CR = 10  
MIN_VOL_RATIO = 2.0
MIN_SHORTLIST_SIZE = 50  # Enforces global cross-sectional parity guardrails
BATCH_SIZE = 100         # Prevents Yahoo Finance API rate-limiting


class AlphaV14Engine:
    def __init__(self, full_universe_list):
        self.tickers = [t + '.NS' if not t.endswith('.NS') else t for t in full_universe_list]
        self.cache = {}
        self.universe = {}
        self.candidates = []
        self.fundamentals = {}
        self.sector_ranks = {}
        self.rs_ranks = {}
        self.today = pd.Timestamp.now()
        self.nifty = pd.Series(dtype=float)
        
        # Setup custom session to mimic standard browser headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        })
        
    def execute(self):
        print("Initializing Alpha V14 Master Ingestion Engine...\n")
        start_time = time.time()
        
        self._pass_0_universe_mapping()
        self._pass_1_catalyst_detection()
        self._pass_2_base_diagnostics()
        self._pass_3_accumulation()
        self._pass_4_rolling_fundamentals()
        df_res = self._pass_5_composite_ranking()
        
        if df_res is not None and not df_res.empty:
            self._export_to_formatted_excel(df_res)
        
        print(f"\nPipeline completed in {round(time.time() - start_time, 2)} seconds.")
        return df_res

    # =========================================================================
    # HELPERS: Momentum & Structural Matrix
    # =========================================================================
    def _calc_adx(self, df, period=14):
        try:
            up_move = df['High'].diff()
            down_move = -df['Low'].diff()
            
            pdm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            mdm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            pdm_s, mdm_s = pd.Series(pdm, index=df.index), pd.Series(mdm, index=df.index)
            
            tr = pd.concat([
                df['High'] - df['Low'], 
                abs(df['High'] - df['Close'].shift(1)), 
                abs(df['Low'] - df['Close'].shift(1))
            ], axis=1).max(axis=1)
            
            atr = tr.ewm(alpha=1/period, adjust=False).mean()
            
            pdi = 100 * (pdm_s.ewm(alpha=1/period, adjust=False).mean() / atr)
            mdi = 100 * (mdm_s.ewm(alpha=1/period, adjust=False).mean() / atr)
            
            dx = (abs(pdi - mdi) / abs(pdi + mdi)) * 100
            return float(dx.ewm(alpha=1/period, adjust=False).mean().iloc[-1])
        except: 
            return 0.0

    def _blended_rs(self, stock, nifty):
        """Institutional Momentum Blend: 20% 1M | 40% 3M | 25% 6M | 15% 12M"""
        try:
            if len(stock) < 252 or len(nifty) < 252: 
                return 1.0
            comp = 0
            for d, w in [(21, 0.2), (63, 0.4), (126, 0.25), (252, 0.15)]:
                p_date = stock.index[-d]
                n_past = nifty.loc[nifty.index >= p_date]
                if not n_past.empty:
                    rs = (stock.iloc[-1] / stock.loc[p_date]) / (nifty.iloc[-1] / n_past.iloc[0])
                    comp += (rs * w)
            return comp
        except: 
            return 1.0

    # =========================================================================
    # PASS 0: BATCHED HIGH SPEED UNIVERSE DOWNLOAD
    # =========================================================================
    def _pass_0_universe_mapping(self):
        print(f"PASS 0: Mapping Universal Data via Batched Stream ({len(self.tickers)} components)...")
        
        # Download Benchmark ^NSEI First
        try:
            nifty_df = yf.download("^NSEI", period="2y", progress=False, auto_adjust=True, session=self.session)
            if 'Close' in nifty_df.columns:
                self.nifty = nifty_df['Close'].dropna()
                if isinstance(self.nifty, pd.DataFrame):
                    self.nifty = self.nifty.iloc[:, 0]
        except Exception as e:
            print(f"[⚠️] Failed to download benchmark Nifty 50 index: {e}")
            self.nifty = pd.Series(dtype=float)

        rs_map = {}
        total_tickers = len(self.tickers)
        
        # Iterate in Chunks of BATCH_SIZE to Avoid Rate Limits
        for i in range(0, total_tickers, BATCH_SIZE):
            chunk = self.tickers[i:i + BATCH_SIZE]
            print(f" -> Fetching Batch [{i + 1} - {min(i + BATCH_SIZE, total_tickers)} / {total_tickers}]...")
            
            try:
                data = yf.download(
                    chunk, 
                    period="2y", 
                    group_by="ticker", 
                    threads=True, 
                    progress=False, 
                    auto_adjust=True,
                    session=self.session
                )
            except Exception as batch_err:
                print(f"[⚠️] Batch execution error: {batch_err}. Skipping chunk.")
                continue

            for t in chunk:
                try:
                    # Parse Ticker Data Out of Multi-Index DataFrame
                    if len(chunk) > 1:
                        if t not in data.columns.levels[0]: 
                            continue
                        hist = data[t].dropna()
                    else:
                        hist = data.dropna()
                        
                    if len(hist) < 255: 
                        continue 
                    
                    self.cache[t] = hist
                    c = float(hist['Close'].iloc[-1])
                    ma50 = hist['Close'].rolling(50).mean()
                    ma150 = hist['Close'].rolling(150).mean()
                    ma200 = hist['Close'].rolling(200).mean()
                    
                    h52 = float(hist['High'].rolling(252).max().iloc[-1])
                    l52 = float(hist['Low'].rolling(252).min().iloc[-1])
                    
                    stage = 0
                    if c > ma150.iloc[-1] and c > ma200.iloc[-1]: stage += 2
                    if ma150.iloc[-1] > ma200.iloc[-1]: stage += 2
                    if ma200.iloc[-1] > ma200.shift(20).iloc[-1]: stage += 2
                    if c > ma50.iloc[-1]: stage += 2
                    if c >= (0.75 * h52) and c >= (1.30 * l52): stage += 2
                    
                    rs = self._blended_rs(hist['Close'], self.nifty) if not self.nifty.empty else 1.0
                    rs_map[t] = rs
                    
                    self.universe[t] = {
                        'Current': c, 
                        'Stage': stage, 
                        'Dist_52W': c / h52 if h52 > 0 else 0, 
                        'ADX': self._calc_adx(hist), 
                        'High_40': float(hist['High'].tail(20).max())
                    }
                except: 
                    pass
            
            # Pause briefly between batches to respect API limits
            time.sleep(1.2)
            
        if rs_map:
            self.rs_ranks = (pd.Series(rs_map).rank(pct=True) * 100).to_dict()

    # =========================================================================
    # PASS 1: DUAL-ENGINE CATALYST TRACKING
    # =========================================================================
    def _pass_1_catalyst_detection(self):
        print("\nPASS 1: Running Dual Engine Catalyst Engines...")
        for t, m in self.universe.items():
            hist = self.cache[t]
            hist['20_Vol'] = hist['Volume'].rolling(20).mean()
            hist['Turnover'] = (hist['Close'] * hist['Volume']) / 10000000
            
            if m['Current'] < MIN_PRICE or float(hist['Turnover'].tail(20).mean()) < MIN_TURNOVER_CR: 
                continue
            if m['Dist_52W'] < 0.75: 
                continue 
            
            recent = hist.tail(60)
            engine_a_event = False
            
            for i in range(len(recent)-1, 0, -1):
                today_row, yest_row = recent.iloc[i], recent.iloc[i-1]
                op_gap = (today_row['Open'] - yest_row['High']) / yest_row['High']
                
                if op_gap > 0.05 and today_row['Volume'] > (yest_row['20_Vol'] * MIN_VOL_RATIO) and today_row['Close'] > today_row['Open']:
                    self.candidates.append({'Symbol': t, 'Type': 'Event', 'Date': recent.index[i]})
                    engine_a_event = True
                    break
                    
            if not engine_a_event and m['Dist_52W'] >= 0.85 and m['Stage'] >= 8:
                tight_5d = (hist['High'].tail(5).max() - hist['Low'].tail(5).min()) / hist['Close'].tail(5).mean()
                if m['ADX'] > 20 or tight_5d < 0.05:
                    self.candidates.append({'Symbol': t, 'Type': 'Silent', 'Date': hist.index[-20]})

    # =========================================================================
    # PASS 2 & 3: VOLATILITY CONTRACTION (VCP) & ACCUMULATION DIAGNOSTICS
    # =========================================================================
    def _pass_2_base_diagnostics(self):
        print("PASS 2: Deconstructing VCP Contraction Waves...")
        for c in self.candidates:
            t = c['Symbol']
            hist = self.cache[t]
            m = self.universe[t]
            
            dist_to_pivot = (m['High_40'] - m['Current']) / m['High_40'] if m['High_40'] > 0 else 1.0
            c['Readiness_Pct'] = dist_to_pivot
            
            last5 = hist.tail(5)
            c['Tight_Pct'] = (last5['High'].max() - last5['Low'].min()) / last5['Close'].mean() if last5['Close'].mean() > 0 else 0
            
            vcp_pts = 0
            if len(hist) >= 20:
                h20, l20 = hist['High'].tail(20).max(), hist['Low'].tail(20).min()
                h10, l10 = hist['High'].tail(10).max(), hist['Low'].tail(10).min()
                h5, l5 = hist['High'].tail(5).max(), hist['Low'].tail(5).min()
                
                r20 = (h20 - l20) / h20 if h20 > 0 else 1.0
                r10 = (h10 - l10) / h10 if h10 > 0 else 1.0
                r5 = (h5 - l5) / h5 if h5 > 0 else 1.0
                
                v20 = hist['Volume'].tail(20).mean()
                v10 = hist['Volume'].tail(10).mean()
                v5 = hist['Volume'].tail(5).mean()
                
                if (r10 < r20 * 0.85) and (r5 < r10 * 0.85): vcp_pts += 5
                elif (r10 < r20) and (r5 < r10): vcp_pts += 2
                if v20 > v10 > v5: vcp_pts += 3
                if l5 >= l10 >= l20: vcp_pts += 2
                    
            c['VCP_Pts'] = vcp_pts

    def _pass_3_accumulation(self):
        print("PASS 3: Evaluating Institutional Volume Sponsorship...")
        for c in self.candidates:
            t = c['Symbol']
            hist = self.cache[t]
            
            c['RVOL'] = float(hist['Volume'].iloc[-1]) / float(hist['20_Vol'].iloc[-1]) if float(hist['20_Vol'].iloc[-1]) > 0 else 1.0
            c['T_Ratio'] = float(hist['Turnover'].tail(20).mean()) / float(hist['Turnover'].tail(50).mean()) if float(hist['Turnover'].tail(50).mean()) > 0 else 1.0
            
            l50 = hist.tail(50)
            up_v = l50[l50['Close'] >= l50['Close'].shift(1)]['Volume'].sum()
            dn_v = l50[l50['Close'] < l50['Close'].shift(1)]['Volume'].sum()
            c['UD_Ratio'] = up_v / dn_v if dn_v > 0 else 1.0

    # =========================================================================
    # PASS 4: ROLLING EARNINGS AVAILABILITY DETECTOR
    # =========================================================================
    def _pass_4_rolling_fundamentals(self):
        print("PASS 4: Parsing Ingested Earnings Pipeline & Freshness Layer...")
        ext_data = pd.DataFrame()
        if os.path.exists(EXTERNAL_FUNDAMENTALS_FILE):
            try:
                ext_data = pd.read_csv(EXTERNAL_FUNDAMENTALS_FILE, index_col='Symbol')
            except: 
                pass
            
        sector_rs = {}
        for t in self.tickers:
            t_clean = t.replace('.NS', '')
            self.fundamentals[t] = {'Sector': 'Unknown', 'Sales_QoQ': 0, 'Profit_QoQ': 0, 'Recency_Pts': 0, 'Date_Str': 'N/A'}
            
            if not ext_data.empty and t_clean in ext_data.index:
                row = ext_data.loc[t_clean]
                sec = row.get('Sector', 'Unknown')
                
                recency_pts = 0
                date_str = "N/A"
                if 'Result_Date' in row and pd.notna(row['Result_Date']):
                    try:
                        r_date = pd.to_datetime(row['Result_Date'], dayfirst=True)
                        days_since = (self.today - r_date).days
                        date_str = r_date.strftime('%Y-%m-%d')
                        
                        if days_since <= 30:   recency_pts = 4  
                        elif days_since <= 95: recency_pts = 2  
                    except: 
                        pass

                self.fundamentals[t] = {
                    'Sector': sec,
                    'Sales_QoQ': float(row.get('Sales_QoQ', 0)) / 100,
                    'Profit_QoQ': float(row.get('Profit_QoQ', 0)) / 100,
                    'Recency_Pts': recency_pts,
                    'Date_Str': date_str
                }
                
                if sec != 'Unknown' and t in self.rs_ranks:
                    if sec not in sector_rs: sector_rs[sec] = []
                    sector_rs[sec].append(self.rs_ranks[t])
                    
        sec_medians = {s: np.median(ranks) for s, ranks in sector_rs.items() if len(ranks) >= 3}
        if sec_medians:
            self.sector_ranks = (pd.Series(sec_medians).rank(pct=True) * 100).to_dict()

    # =========================================================================
    # PASS 5: ALPHA V14 COMPOSITE SCORE (100 POINT RISK MATRIX)
    # =========================================================================
    def _pass_5_composite_ranking(self):
        print("PASS 5: Structuring Unified Institutional Leadership Board...\n")
        results = []
        
        for c in self.candidates:
            t = c['Symbol']
            m = self.universe[t]
            f = self.fundamentals[t]
            rs_rnk = self.rs_ranks.get(t, 0)
            sec_rnk = self.sector_ranks.get(f['Sector'], 0)

            ts = 0
            if rs_rnk >= 95: ts += 20
            elif rs_rnk >= 90: ts += 15
            elif rs_rnk >= 80: ts += 10
            elif rs_rnk >= 70: ts += 5
            ts += m['Stage'] 
            
            d52 = m['Dist_52W']
            if d52 >= 0.95: ts += 10
            elif d52 >= 0.90: ts += 7
            elif d52 >= 0.85: ts += 4
            
            dist_pvt = c['Readiness_Pct']
            if dist_pvt <= 0.02: ts += 10
            elif dist_pvt <= 0.05: ts += 5

            ss = c['VCP_Pts']
            tight = c['Tight_Pct']
            if tight <= 0.03: ss += 10
            elif tight <= 0.05: ss += 5

            acs = 0
            if c['UD_Ratio'] >= 1.5: acs += 5
            elif c['UD_Ratio'] >= 1.2: acs += 3
            
            rvol = c['RVOL']
            if rvol >= 3.0: acs += 5
            elif rvol >= 2.0: acs += 3
            elif rvol >= 1.5: acs += 1
            
            tr = c['T_Ratio']
            if tr >= 1.5: acs += 5
            elif tr >= 1.2: acs += 3

            fs = 0
            if f['Sales_QoQ'] > 0.20: fs += 4
            elif f['Sales_QoQ'] > 0.10: fs += 2
            
            if f['Profit_QoQ'] > 0.25: fs += 4
            elif f['Profit_QoQ'] > 0.15: fs += 2
            
            if sec_rnk >= 80: fs += 3
            elif sec_rnk >= 60: fs += 1
            
            fs += f['Recency_Pts']

            total = ts + ss + acs + fs
            sig = "🏆 LEADER" if total >= 80 else ("⭐ READY" if total >= 65 else "🔵 WATCH")

            results.append({
                'Symbol': t.replace('.NS', ''),
                'Type': c['Type'],
                'Score': int(total),
                'Tech': ts, 'Strc': ss, 'Acc': acs, 'Fund': fs,
                'RS_Rnk': int(rs_rnk),
                'Earnings_Date': f['Date_Str'],
                'Read%': f"{round(dist_pvt*100, 1)}%",
                'Tight': f"{round(tight*100, 1)}%",
                'Signal': sig
            })

        if not results:
            print("No active cataloged setup candidates passed baseline rules.")
            return None

        df = pd.DataFrame(results).sort_values(by='Score', ascending=False).reset_index(drop=True)
        
        print("============================================================================================================")
        print("📈 ALPHA V14: ROLLING EVENT-INTEGRATED INSTITUTIONAL MATRIX")
        print("============================================================================================================")
        print(f"{'Symbol':<12} {'Type':<7} {'Score':<5} {'Tech':<5} {'Strc':<5} {'Acc':<5} {'Fund':<5} {'RS_Rnk':<6} {'Reported':<11} {'Read%':<6} {'Tight':<6} {'Signal'}")
        print("-" * 116)
        for _, r in df.iterrows():
            print(f"{r['Symbol']:<12} {r['Type']:<7} {r['Score']:<5} {r['Tech']:<5} {r['Strc']:<5} {r['Acc']:<5} {r['Fund']:<5} {r['RS_Rnk']:<6} {r['Earnings_Date']:<11} {r['Read%']:<6} {r['Tight']:<6} {r['Signal']}")
            
        return df

    def _export_to_formatted_excel(self, df):
        print(f"\n📁 Deploying visual layout formats to spreadsheet: {OUTPUT_EXCEL_FILE}...")
        try:
            with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Alpha Alpha V14 Board", index=False)
                workbook = writer.book
                worksheet = writer.sheets["Alpha Alpha V14 Board"]
                
                for col in worksheet.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = col[0].column_letter
                    worksheet.column_dimensions[col_letter].width = max(max_len + 3, 11)
            print("[+] Export Success: Matrix generated cleanly with safe header widths.")
        except Exception as sheet_err:
            print(f"[⚠️] Spreadsheet IO write block dropped: {sheet_err}")


# =============================================================================
# HARD UNIVERSE LOADING & PROTECTION RECONCILIATION ROUTINE
# =============================================================================
def load_symbols():
    if not os.path.exists(CSV_PATH): 
        raise FileNotFoundError(f"❌ Core configuration manifest missing at: {CSV_PATH}")
    try:
        df = pd.read_csv(CSV_PATH)
        df.columns = [c.strip().upper() for c in df.columns]
        if "SERIES" in df.columns: 
            df = df[df["SERIES"] == "EQ"]
        symbols = df["SYMBOL"].dropna().astype(str).str.strip().str.upper().unique().tolist()
        return [s for s in symbols if len(s) >= 2 and not any(x in s for x in ["/", "\\", " ", "&", "*"])]
    except Exception as e:
        print(f"[-] Critical system fault mapping csv arrays: {e}")
        return []

if __name__ == "__main__":
    print("\n=======================================================")
    print("📈 ALPHA V14 PIPELINE: AUTOMATED UNIVERSE AGGREGATOR")
    print("=======================================================\n")
    
    universe_watchlist = []
    
    # Adaptive Shortlist Integration Check Passage Rules
    if os.path.exists(SHORTLIST_INPUT_PATH):
        try:
            shortlist_df = pd.read_excel(SHORTLIST_INPUT_PATH)
            shortlist_df.columns = shortlist_df.columns.str.strip().str.lower()
            
            for col in ["ticker", "symbol", "stock"]:
                if col in shortlist_df.columns:
                    shortlist_df.rename(columns={col: "ticker"}, inplace=True)
                    break
                    
            if "ticker" in shortlist_df.columns:
                candidates = shortlist_df["ticker"].dropna().astype(str).str.strip().str.upper().tolist()
                n = len(candidates)
                
                if n >= MIN_SHORTLIST_SIZE:
                    universe_watchlist = candidates
                    print(f"✅ Protection Matrix Cleared: Using Fundamental Shortlist ({n} tickers loaded).")
                else:
                    print(f"⚠️ Scale Degradation Warning: Shortlist has only {n} lines (Required Minimum: {MIN_SHORTLIST_SIZE}).")
                    print("   Halting micro-slice; falling back to full cross-sectional universe parity.")
                    universe_watchlist = load_symbols()
            else:
                print("⚠️ Identification header missing inside Shortlist spreadsheet. Parsing fallback.")
                universe_watchlist = load_symbols()
        except Exception as err:
            print(f"[⚠️] Shortlist file stream corrupted: {err}. Parsing fallback.")
            universe_watchlist = load_symbols()
    else:
        print("📡 Shortlist spreadsheet absent from asset directories. Initializing standard market load.")
        universe_watchlist = load_symbols()

    if not universe_watchlist:
        print("❌ Execution Refused: Target asset watchlist is empty.")
    else:
        pipeline = AlphaV14Engine(universe_watchlist)
        pipeline.execute()