"""
Execution_Plan_Generator.py
-------------------------------------------------------------------------

Execution Decision Layer

Input:
    trade_candidates

Output:
    execution_plan

Purpose:
    Converts risk-managed candidates into actionable
    breakout execution plans.

No broker dependency.
Paper execution only.

-------------------------------------------------------------------------

"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

from core.config import DB_PATH, PARQUET_CACHE_DIR



class ExecutionPlanGenerator:


    def __init__(
        self,
        breakout_buffer=0.02,
        max_extension=0.05
    ):

        """
        breakout_buffer:
            Allow entry slightly above pivot

        max_extension:
            Reject stocks extended too far above pivot
        """

        self.breakout_buffer = breakout_buffer
        self.max_extension = max_extension



    # ---------------------------------------------------
    # Normalize ticker
    # ---------------------------------------------------

    def normalize_ticker(self,ticker):

        return (
            str(ticker)
            .replace(".NS","")
            .upper()
            .strip()
        )



    # ---------------------------------------------------
    # Get current price from bhav-copy-derived parquet cache
    # ---------------------------------------------------

    def get_current_price(self, ticker, fallback_price):
        """
        Reads the most recent closing price for a ticker from the
        bhav-copy-derived parquet cache. This runs as part of the nightly
        batch pipeline (after market close), so today's closing price is
        the correct "current price" - no live feed needed.

        Falls back to the given price (the pivot) if the parquet file is
        missing or unreadable, preserving the previous safe behavior
        rather than crashing.
        """

        path = os.path.join(
            PARQUET_CACHE_DIR,
            f"{ticker}.parquet"
        )

        if not os.path.exists(path):
            return fallback_price

        try:
            df = pd.read_parquet(path)

            if df.empty:
                return fallback_price

            latest = df.sort_values("date").iloc[-1]

            return float(latest["close"])

        except Exception:
            return fallback_price



    # ---------------------------------------------------
    # Generate Execution Plan
    # ---------------------------------------------------

    def generate(self):


        conn=sqlite3.connect(DB_PATH)



        print()
        print("="*75)
        print("📋 EXECUTION PLAN GENERATOR")
        print("="*75)



        try:

            trades=pd.read_sql(
                """
                SELECT *

                FROM trade_candidates

                """,
                conn
            )


        except Exception as e:

            print(
                "[!] trade_candidates missing:",
                e
            )

            conn.close()
            return 0



        if trades.empty:

            print(
                "[!] No trade candidates found"
            )

            conn.close()
            return 0



        print(
            f"Candidates Loaded : {len(trades)}"
        )



        execution=[]



        for _,row in trades.iterrows():


            ticker=row["ticker"]


            pivot=float(
                row["pivot"]
            )


            stop=float(
                row["stop_loss"]
            )


            target1=float(
                row["target_1"]
            )


            target2=float(
                row["target_2"]
            )


            quantity=int(
                row.get(
                    "recommended_quantity",
                    row.get(
                        "shares",
                        0
                    )
                )
            )



            current_price = self.get_current_price(
                self.normalize_ticker(ticker),
                fallback_price=pivot,
            )



            breakout_level=pivot



            entry_low=pivot


            entry_high=(

                pivot *
                (1+self.breakout_buffer)

            )



            extension=(

                current_price-pivot

            )/pivot




            # -------------------------------
            # Decision Logic
            # -------------------------------


            if extension > self.max_extension:


                state="EXTENDED"

                allowed=0



            elif current_price >= breakout_level:


                state="VALID_BREAKOUT"

                allowed=1



            else:


                state="WAITING_BREAKOUT"

                allowed=0




            execution.append({


                "ticker":
                self.normalize_ticker(
                    ticker
                ),


                "pivot":
                pivot,


                "entry_low":
                round(
                    entry_low,
                    2
                ),


                "entry_high":
                round(
                    entry_high,
                    2
                ),


                "stop_loss":
                stop,


                "target_1":
                target1,


                "target_2":
                target2,


                "recommended_quantity":
                quantity,


                "composite_score":
                row.get(
                    "composite_score",
                    0
                ),


                "pattern":
                row.get(
                    "pattern",
                    "UNKNOWN"
                ),


                "execution_state":
                state,


                "allowed_to_trade":
                allowed,


                "created_date":
                datetime.now()
                .strftime("%Y-%m-%d")

            })




        df=pd.DataFrame(execution)



        #
        # Save execution table
        #

        df.to_sql(
            "execution_plan",
            conn,
            if_exists="replace",
            index=False
        )


        conn.close()



        print()
        print(
            f"[+] Execution Plans Created : {len(df)}"
        )


        print(
            "Execution States:"
        )


        print(
            df["execution_state"]
            .value_counts()
        )


        print("="*75)



        return len(df)




if __name__=="__main__":


    engine=ExecutionPlanGenerator()

    engine.generate()