"""
Risk_Positioning_Engine.py
-------------------------------------------------------------------------

Institutional Risk & Positioning Compiler

Pipeline Position:
Master_Terminal
        |
        ↓
research_watchlist
        |
        +---- JOIN ----+
                       |
                execution_plan
                       |
                       ↓
             Risk Calculation
                       |
                       ↓
              trade_candidates


Fixes:
- Correct input source alignment
- Joins research_watchlist + execution_plan
- Handles missing ATR values
- Generates complete trade plans
- Prevents duplicate tickers
- Preserves execution fields
"""

import sqlite3
from datetime import datetime

import pandas as pd
import numpy as np

from core.config import DB_PATH


class RiskPositioningEngine:

    def __init__(
        self,
        total_capital: float = 1000000,
        risk_per_trade_pct: float = 0.005
    ):
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct


    # ---------------------------------------------------------
    # MARKET REGIME
    # ---------------------------------------------------------

    def fetch_latest_market_regime(self, conn):

        try:

            df = pd.read_sql(
                """
                SELECT 
                    regime,
                    composite_score,
                    confidence,
                    position_multiplier

                FROM market_regime

                ORDER BY date DESC

                LIMIT 1
                """,
                conn
            )


            if df.empty:
                return {
                    "regime": "NEUTRAL",
                    "multiplier": 0.25
                }


            row = df.iloc[0]

            return {

                "regime": row["regime"],

                "multiplier":
                    float(row.get(
                        "position_multiplier",
                        0.25
                    ))
            }


        except Exception:

            return {
                "regime": "NEUTRAL",
                "multiplier": 0.25
            }



    # ---------------------------------------------------------
    # LOAD RESEARCH + EXECUTION DATA
    # ---------------------------------------------------------

    def load_execution_universe(self, conn):

        query = """

        SELECT

            rw.Ticker                         AS ticker,

            rw.Composite_Score                AS composite_score,

            rw.Confidence_Adjusted_Score      AS confidence_score,

            rw.Tier                           AS tier,

            rw.pattern                        AS pattern,

            rw.pattern_confidence             AS pattern_confidence,


            ep.pivot_price                    AS pivot,

            ep.pivot_source                   AS pivot_source,

            ep.pivot_confidence               AS pivot_strength,

            ep.atr_14                         AS atr14


        FROM research_watchlist rw


        LEFT JOIN execution_plan ep


        ON REPLACE(
            UPPER(rw.Ticker),
            '.NS',
            ''
        )

        =
        
        REPLACE(
            UPPER(ep.ticker),
            '.NS',
            ''
        )


        WHERE rw.Readiness =
        'Immediate Trigger Watch'


        """


        df = pd.read_sql(query, conn)


        return df



    # ---------------------------------------------------------
    # RISK COMPILATION
    # ---------------------------------------------------------

    def compile_risk_and_positioning(self):


        conn = sqlite3.connect(DB_PATH)


        regime = self.fetch_latest_market_regime(conn)


        print("\n")
        print("=" * 70)
        print("🛡️  RISK & POSITIONING COMPILER")
        print("=" * 70)


        print(
            f"[*] Market Regime : {regime['regime']}"
        )

        print(
            f"[*] Exposure      : "
            f"{regime['multiplier']*100:.0f}%"
        )


        df = self.load_execution_universe(conn)



        print(
            f"\n[*] Research Candidates Loaded : {len(df)}"
        )


        if df.empty:

            print(
                "[!] No research candidates available"
            )

            conn.close()
            return 0



        exposure_multiplier = regime["multiplier"]


        effective_capital = (
            self.total_capital *
            exposure_multiplier
        )


        risk_budget = (
            effective_capital *
            self.risk_per_trade_pct
        )


        records = []


        for _, row in df.iterrows():


            ticker = row["ticker"]


            pivot = row["pivot"]


            if pd.isna(pivot) or pivot <= 0:

                continue



            #
            # ATR Handling
            #

            atr = row["atr14"]


            if pd.isna(atr) or atr <= 0:

                atr = pivot * 0.03


            atr = float(atr)



            #
            # Structural Stop
            #

            stop_loss = (
                pivot -
                (1.5 * atr)
            )


            risk_per_share = (
                pivot -
                stop_loss
            )



            if risk_per_share <= 0:

                continue



            #
            # Position Size
            #

            shares = int(
                risk_budget /
                risk_per_share
            )


            position_value = (
                shares *
                pivot
            )



            #
            # Targets
            #

            target_1 = (
                pivot +
                (2 * risk_per_share)
            )


            target_2 = (
                pivot +
                (3 * risk_per_share)
            )



            records.append({

                "ticker":
                    ticker,


                "pivot":
                    round(pivot,2),


                "pattern":
                    row.get(
                        "pattern",
                        "UNKNOWN"
                    ),


                "confidence":
                    row.get(
                        "pattern_confidence",
                        0
                    ),


                "atr14":
                    round(
                        atr,
                        2
                    ),


                "stop_loss":
                    round(
                        stop_loss,
                        2
                    ),


                "target_1":
                    round(
                        target_1,
                        2
                    ),


                "target_2":
                    round(
                        target_2,
                        2
                    ),


                "risk_per_share":
                    round(
                        risk_per_share,
                        2
                    ),


                "composite_score":
                    row.get(
                        "composite_score",
                        0
                    ),


                "tier":
                    row.get(
                        "tier",
                        "UNKNOWN"
                    ),


                "shares":
                    shares,


                "position_value":
                    round(
                        position_value,
                        2
                    ),


                "date":
                    datetime.now()
                    .strftime("%Y-%m-%d")

            })



        df_trade = pd.DataFrame(records)



        if df_trade.empty:

            print(
                "\n[!] No actionable setups compiled"
            )

            conn.close()

            return 0



        #
        # Remove duplicate NSE/non NSE symbols
        #

        df_trade["clean"] = (
            df_trade["ticker"]
            .astype(str)
            .str.replace(
                ".NS",
                "",
                regex=False
            )
            .str.upper()
        )


        df_trade = (
            df_trade
            .drop_duplicates(
                subset=["clean"],
                keep="first"
            )
            .drop(
                columns=["clean"]
            )
        )



        #
        # Save output
        #

        df_trade.to_sql(
            "trade_candidates",
            conn,
            if_exists="replace",
            index=False
        )


        conn.close()



        print(
            f"\n[+] Risk Plans Generated : "
            f"{len(df_trade)}"
        )


        print(
            "[+] trade_candidates updated"
        )


        print("=" * 70)



        return len(df_trade)




if __name__ == "__main__":


    engine = RiskPositioningEngine(
        total_capital=1000000,
        risk_per_trade_pct=0.005
    )


    engine.compile_risk_and_positioning()
