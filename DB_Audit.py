import sqlite3
import pandas as pd

from core.config import DB_PATH


def run():

    conn = sqlite3.connect(DB_PATH)

    print("\n==============================")
    print("DATABASE TABLE INVENTORY")
    print("==============================")

    tables = pd.read_sql(
        """
        SELECT name 
        FROM sqlite_master 
        WHERE type='table'
        ORDER BY name
        """,
        conn
    )

    for t in tables["name"]:
        print(t)


    print("\n==============================")
    print("RESEARCH WATCHLIST HEALTH")
    print("==============================")


    try:

        df = pd.read_sql(
            "SELECT * FROM research_watchlist WHERE Date = (SELECT MAX(Date) FROM research_watchlist)",
            conn
        )

        print("Rows:", len(df))


        if not df.empty:

            print("\nTier Distribution")
            print(
                df["Tier"]
                .value_counts()
            )


            print("\nOpportunity Distribution")
            print(
                df["Opportunity"]
                .value_counts()
            )


            print("\nReadiness Distribution")
            print(
                df["Readiness"]
                .value_counts()
            )


            print("\nTop 10 Scores")

            cols = [
                "Ticker",
                "Composite_Score",
                "Confidence_Adjusted_Score",
                "Tier",
                "Readiness"
            ]

            print(
                df.sort_values(
                    "Confidence_Adjusted_Score",
                    ascending=False
                )[cols]
                .head(10)
                .to_string(index=False)
            )


    except Exception as e:

        print(
            "research_watchlist error:",
            e
        )



    print("\n==============================")
    print("TRADE CANDIDATES")
    print("==============================")


    try:

        trade = pd.read_sql(
            "SELECT * FROM trade_candidates",
            conn
        )

        print(
            "trade_candidates rows:",
            len(trade)
        )

        if not trade.empty:
            print(
                trade.head(10)
                .to_string(index=False)
            )


    except Exception as e:

        print(
            "trade_candidates error:",
            e
        )


    conn.close()



if __name__ == "__main__":
    run()