"""
Risk_Positioning_Engine.py
------------------------------------------------------------

Research Watchlist
        +
Execution Plan
        |
        ↓
Risk Compiler
        |
        ↓
trade_candidates

"""

import sqlite3
from datetime import datetime

import pandas as pd

from core.config import DB_PATH
from core.kill_switch import check_kill_switch
from core.technical_indicators import compute_atr
from core.sector_map import get_sector


# Base R:R stays 2:1/3:1 (the original, reasonable baseline) - real
# improvement comes from adjusting AROUND that baseline based on market
# regime and setup quality, rather than applying the same fixed
# multiplier to every single trade regardless of context.
REGIME_RR_ADJUSTMENT = {
    "CONFIRMED_UPTREND": 1.2,
    "EARLY_RECOVERY": 1.0,
    "CHOPPY_ACCUMULATION": 0.9,
    "DISTRIBUTION": 0.7,
    "BEAR": 0.6,
}


def calculate_dynamic_rr_multipliers(regime, composite_score):
    """
    Known limitation: Composite_Score is the only setup-quality signal
    available at this stage of the pipeline (this runs end-of-day,
    before the live intraday data the newer conviction score in
    Live_Execution_Monitor.py depends on even exists) - it's the best
    available signal here, not a perfectly differentiated one (see the
    Master_Terminal.py tier-assignment fix for the known small-pool
    saturation issue this doesn't fully resolve).
    """

    try:
        cs = float(composite_score)
    except (TypeError, ValueError):
        cs = 0.5

    regime_factor = REGIME_RR_ADJUSTMENT.get(regime, 0.85)
    quality_factor = 0.85 + (cs * 0.30)
    combined = regime_factor * quality_factor

    t1_multiplier = round(2.0 * combined, 2)
    t2_multiplier = round(3.0 * combined, 2)

    return t1_multiplier, t2_multiplier


class RiskPositioningEngine:

    def __init__(
        self,
        total_capital=1000000,
        risk_per_trade_pct=0.005
    ):
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct

    def get_market_regime(self, conn):
        try:
            df = pd.read_sql(
                """
                SELECT *
                FROM market_regime
                ORDER BY date DESC
                LIMIT 1
                """,
                conn
            )

            if df.empty:
                return 0.25, "NEUTRAL"

            row = df.iloc[0]

            # Prefer the VIX-adjusted multiplier when available - a real
            # complementary volatility cross-check on top of the
            # breadth-based exposure. Falls back to the plain
            # breadth-based value if VIX data wasn't available that day
            # (older rows, or a failed live fetch), never breaks.
            vix_adjusted = row.get("vix_adjusted_multiplier")

            if vix_adjusted is not None and pd.notna(vix_adjusted):
                multiplier = float(vix_adjusted)
            else:
                multiplier = float(row.get("position_multiplier", 0.25))

            return (
                multiplier,
                str(row.get("regime", "NEUTRAL"))
            )

        except:
            return 0.25, "NEUTRAL"

    def load_candidates(self, conn):
        query = """
        SELECT
        rw.Ticker,
        rw.Composite_Score,
        rw.Tier,
        rw.pattern,
        rw.pattern_confidence,
        cp.pivot_price,
        cp.confidence AS pivot_confidence,
        NULL AS atr_14
        FROM research_watchlist rw
        LEFT JOIN consensus_pivots cp
        ON REPLACE(
            UPPER(rw.Ticker),
            '.NS',
            ''
        )
        =
        REPLACE(
            UPPER(cp.ticker),
            '.NS',
            ''
        )
        AND cp.date = (SELECT MAX(date) FROM consensus_pivots)
        WHERE rw.Readiness =
        'Immediate Trigger Watch'
        AND rw.Date = (SELECT MAX(Date) FROM research_watchlist)
        """

        df = pd.read_sql(
            query,
            conn
        )

        if df.empty:
            return df

        # normalize ticker
        df["clean"] = (
            df["Ticker"]
            .astype(str)
            .str.replace(
                ".NS",
                "",
                regex=False
            )
            .str.upper()
        )

        #
        # keep one pivot per stock
        #
        df = (
            df
            .sort_values(
                "pivot_confidence",
                ascending=False
            )
            .drop_duplicates(
                "clean"
            )
        )

        return df

    def run(self):
        conn = sqlite3.connect(DB_PATH)

        print()
        print("="*70)
        print("🛡️ RISK & POSITIONING COMPILER")
        print("="*70)

        multiplier, regime = self.get_market_regime(conn)

        print(
            f"Exposure Multiplier : {multiplier*100:.0f}%"
        )

        df = self.load_candidates(conn)

        print(
            f"Research Candidates : {len(df)}"
        )

        if df.empty:
            print(
                "[!] No candidates received"
            )
            conn.close()
            return

        kill_switch_result = check_kill_switch(self.total_capital)

        if kill_switch_result["blocked"]:
            print()
            print(f"🛑 KILL SWITCH ACTIVE [{kill_switch_result['severity']}]")
            print(f"   {kill_switch_result['reason']}")
            print("   No new positions will be sized this run.")
            conn.close()
            return

        capital = (
            self.total_capital *
            multiplier
        )

        risk_budget = (
            capital *
            self.risk_per_trade_pct
        )

        # Portfolio-wide governance - real gaps found while investigating
        # an unconnected paper-trading cluster tonight (Portfolio_Risk_
        # Controller.py had a MAX_POSITIONS concept nothing else in this
        # system had). Since this script generates candidates, not
        # actual executions, it can't know which ones you'll take - so
        # rather than silently drop specific candidates, it checks your
        # REAL current open positions (from trade_journal) and warns
        # clearly if you're already at or near a sensible ceiling.
        MAX_POSITIONS = 10
        MAX_PER_SECTOR = 3

        try:
            open_count = conn.execute(
                "SELECT COUNT(*) FROM trade_journal WHERE status='EXECUTED'"
            ).fetchone()[0]
        except Exception:
            open_count = 0

        if open_count >= MAX_POSITIONS:
            print(f"[!] PORTFOLIO WARNING: {open_count} real open positions already logged "
                  f"(ceiling {MAX_POSITIONS}) - consider whether taking new positions tonight makes sense.")
        elif open_count >= MAX_POSITIONS * 0.8:
            print(f"[*] {open_count} real open positions logged - approaching the {MAX_POSITIONS} ceiling.")

        # Sector concentration - flags, never excludes. A candidate that
        # would push a sector past MAX_PER_SECTOR is still sized and
        # included normally; it just carries a clear warning so you can
        # weigh it yourself, rather than making a genuinely good setup
        # silently disappear from the board. Only actually protects
        # candidates within our curated sector mapping (core/sector_map.py,
        # now expanded to 212 real, NSE-sourced stocks) - anything else
        # returns UNKNOWN and never gets this warning.
        sector_counts = {}

        output = []

        for _, row in df.iterrows():
            pivot = row["pivot_price"]

            if pd.isna(pivot):
                continue

            sector = get_sector(row["Ticker"])

            sector_warning = None
            if sector != "UNKNOWN" and sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
                sector_warning = (
                    f"SECTOR CONCENTRATION - {sector_counts[sector]} other {sector} "
                    f"candidates already in this batch"
                )

            #
            # ATR - try a real, stock-specific calculation first, using
            # the same technical_indicators module the live monitor uses.
            # Only falls back to the flat 3%-of-pivot estimate if there
            # genuinely isn't enough history yet for that specific stock.
            #
            atr = row["atr_14"]

            if pd.isna(atr):
                clean_ticker_for_atr = str(row["Ticker"]).replace(".NS", "").upper().strip()
                real_atr, _ = compute_atr(clean_ticker_for_atr)
                atr = real_atr if real_atr is not None else pivot * 0.03

            stop = (
                pivot -
                (1.5 * atr)
            )

            risk = (
                pivot -
                stop
            )

            if risk <= 0:
                continue

            shares = int(
                risk_budget / risk
            )

            # 20% concentration cap - a stock with a very tight stop
            # (small risk_per_share) can otherwise pass pure risk-based
            # sizing with far more capital than sensible for a single
            # position. Real testing showed this could recommend
            # oversized positions in low-priced, tight-stop stocks -
            # capping here matches Alpha1's own approach.
            max_shares_by_concentration = int(
                (self.total_capital * 0.20) / pivot
            )

            concentration_capped = shares > max_shares_by_concentration

            if concentration_capped:
                shares = max_shares_by_concentration

            if shares <= 0:
                continue

            if sector != "UNKNOWN":
                sector_counts[sector] = sector_counts.get(sector, 0) + 1

            t1_mult, t2_mult = calculate_dynamic_rr_multipliers(
                regime,
                row.get("Composite_Score", 0.5)
            )

            output.append({
                "ticker":
                row["Ticker"],

                "sector":
                sector,

                "sector_warning":
                sector_warning,

                "pivot":
                round(
                    pivot,
                    2
                ),

                "pattern":
                row["pattern"],

                "confidence":
                row["pattern_confidence"],

                "atr14":
                round(
                    atr,
                    2
                ),

                "stop_loss":
                round(
                    stop,
                    2
                ),

                "target_1":
                round(
                    pivot + t1_mult * risk,
                    2
                ),

                "target_2":
                round(
                    pivot + t2_mult * risk,
                    2
                ),

                "risk_per_share":
                round(
                    risk,
                    2
                ),

                "composite_score":
                row["Composite_Score"],

                "tier":
                row["Tier"],

                "shares":
                shares,

                "date":
                datetime.now()
                .strftime("%Y-%m-%d")
            })

        result = pd.DataFrame(output)

        if result.empty:
            print(
                "[!] No risk plans created"
            )
            conn.close()
            return

        result.to_sql(
            "trade_candidates",
            conn,
            if_exists="replace",
            index=False
        )

        conn.close()

        print(
            f"[+] Trade Plans Generated : {len(result)}"
        )
        print(
            "[+] trade_candidates updated"
        )
        print("="*70)


if __name__ == "__main__":
    while True:
        capital_input = input(
            "Enter your available trading capital for today (Rs): "
        ).strip()

        try:
            capital_value = float(capital_input)

            if capital_value <= 0:
                print("Capital must be a positive number. Please try again.")
                continue

            break

        except ValueError:
            print("Please enter a valid number (e.g. 500000).")

    while True:
        risk_input = input(
            "Enter risk per trade as a percentage (e.g. 1 for 1%): "
        ).strip()

        try:
            risk_pct_value = float(risk_input)

            if risk_pct_value <= 0:
                print("Risk percentage must be positive. Please try again.")
                continue

            if risk_pct_value > 5:
                print(
                    f"WARNING: {risk_pct_value}% per trade is above the "
                    f"commonly-cited 1-2% range and is generally considered "
                    f"aggressive. Proceeding with your value."
                )

            break

        except ValueError:
            print("Please enter a valid number (e.g. 1 or 0.5).")

    engine = RiskPositioningEngine(
        total_capital=capital_value,
        risk_per_trade_pct=risk_pct_value / 100
    )

    engine.run()