import pandas as pd
import os

FILE_PATH = "Stocks_Holdings_Statement.csv"


def load_portfolio(file_path=FILE_PATH):
    try:
        print("📂 Loading portfolio from CSV...")

        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])

        # Try normal read
        df = pd.read_csv(file_path)

        # If empty or weird → try skipping rows
        if df.shape[1] == 1:
            df = pd.read_csv(file_path, skiprows=1)

        print("\n🔍 Detected Columns:", list(df.columns))

        # -------------------------
        # FLEXIBLE COLUMN DETECTION
        # -------------------------
        stock_col = None
        qty_col = None
        price_col = None

        for col in df.columns:
            col_upper = col.upper()

            if any(x in col_upper for x in ["STOCK", "SYMBOL", "INSTRUMENT", "SECURITY", "TRADING"]):
                stock_col = col

            if any(x in col_upper for x in ["QTY", "QUANTITY"]):
                qty_col = col

            if any(x in col_upper for x in ["PRICE", "AVG", "COST"]):
                price_col = col

        # -------------------------
        # VALIDATION
        # -------------------------
        if stock_col is None:
            print("❌ Could not detect stock column automatically")
            return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])

        print(f"✅ Using Stock column: {stock_col}")

        # Extract columns
        df_out = pd.DataFrame()
        df_out["Stock"] = df[stock_col]

        if qty_col:
            print(f"✅ Using Qty column: {qty_col}")
            df_out["Qty"] = df[qty_col]
        else:
            print("⚠️ Qty column not found → default 0")
            df_out["Qty"] = 0

        if price_col:
            print(f"✅ Using Price column: {price_col}")
            df_out["AvgPrice"] = df[price_col]
        else:
            print("⚠️ Price column not found → default 0")
            df_out["AvgPrice"] = 0

        # -------------------------
        # CLEANING
        # -------------------------
        df_out["Stock"] = (
            df_out["Stock"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        df_out = df_out[df_out["Stock"] != "NAN"]
        df_out = df_out[df_out["Stock"] != ""]

        df_out["Qty"] = pd.to_numeric(df_out["Qty"], errors="coerce").fillna(0)
        df_out["AvgPrice"] = pd.to_numeric(df_out["AvgPrice"], errors="coerce").fillna(0)

        df_out = df_out.drop_duplicates(subset=["Stock"], keep="last")

        df_out.reset_index(drop=True, inplace=True)

        print(f"\n✅ Loaded {len(df_out)} holdings")

        return df_out

    except Exception as e:
        print(f"❌ Portfolio loading failed: {e}")
        return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])


# -------------------------
# RUN TEST
# -------------------------
if __name__ == "__main__":
    portfolio = load_portfolio()

    print("\n📊 PORTFOLIO SNAPSHOT:")
    print(portfolio.head(20))

    print("\n📈 SUMMARY:")
    print(f"Total Stocks: {len(portfolio)}")
    print(f"Total Quantity: {portfolio['Qty'].sum()}")