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

                return 0.25


            return float(
                df.iloc[0]
                .get(
                    "position_multiplier",
                    0.25
                )
            )


        except:

            return 0.25



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



        multiplier = self.get_market_regime(conn)


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



        capital = (
            self.total_capital *
            multiplier
        )


        risk_budget = (
            capital *
            self.risk_per_trade_pct
        )



        output=[]



        for _,row in df.iterrows():


            pivot=row["pivot_price"]


            if pd.isna(pivot):

                continue



            #
            # ATR fallback
            #

            atr=row["atr_14"]


            if pd.isna(atr):

                atr=pivot*0.03



            stop = (
                pivot -
                (1.5*atr)
            )


            risk = (
                pivot -
                stop
            )



            if risk<=0:

                continue



            shares=int(
                risk_budget/risk
            )


            if shares<=0:

                continue



            output.append({

                "ticker":
                row["Ticker"],


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
                    pivot+2*risk,
                    2
                ),


                "target_2":
                round(
                    pivot+3*risk,
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



        result=pd.DataFrame(output)



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




if __name__=="__main__":

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


    engine=RiskPositioningEngine(
        total_capital=capital_value,
        risk_per_trade_pct=risk_pct_value/100
    )

    engine.run()