import sqlite3
import pandas as pd

from core.config import DB_PATH


conn = sqlite3.connect(DB_PATH)


print("\n==============================================")
print("RISK ENGINE INPUT AUDIT")
print("==============================================\n")


# Research Watchlist

rw = pd.read_sql(
    "SELECT * FROM research_watchlist",
    conn
)

print("research_watchlist rows :", len(rw))

print("\nColumns:")
print(list(rw.columns))


print("\nReadiness Distribution")

if "Readiness" in rw.columns:
    print(
        rw["Readiness"]
        .value_counts()
    )


print("\nSample")

print(
    rw.head(5)
)


# Execution Plan

print("\n==============================================")

ep = pd.read_sql(
    "SELECT * FROM execution_plan",
    conn
)

print("execution_plan rows :", len(ep))

print("\nColumns:")
print(list(ep.columns))


print("\nSample")

print(
    ep.head(5)
)


# Test Join

print("\n==============================================")
print("JOIN TEST")
print("==============================================")

query = """

SELECT

rw.Ticker,
rw.Readiness,
ep.ticker,
ep.pivot_price

FROM research_watchlist rw

LEFT JOIN execution_plan ep

ON REPLACE(
UPPER(rw.Ticker),
'.NS',
'')

=

REPLACE(
UPPER(ep.ticker),
'.NS',
'')


LIMIT 20

"""


join_test = pd.read_sql(query, conn)


print(join_test)


print("\nMatched pivots:")

print(
    join_test["pivot_price"]
    .notna()
    .sum()
)


conn.close()
