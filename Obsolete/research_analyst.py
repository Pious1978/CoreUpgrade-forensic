import pandas as pd
import os
import config  # <--- Centralized settings

def save_with_retry(df, filename):
    """Ensures the script doesn't crash if Excel is open."""
    while True:
        try:
            df.to_excel(filename, sheet_name='Sheet1', index=False)
            print(f"✅ Successfully updated {filename}!")
            break
        except PermissionError:
            print(f"\n⚠️ ERROR: Access Denied to '{filename}'.")
            print("👉 Please CLOSE the Excel file if it is open.")
            input("Press Enter once you have closed the file to try again...")
        except Exception as e:
            print(f"❌ Unexpected Error during save: {e}")
            break

def update_trade_sheet():
    print(f"--- Piyoosh's Trade Sheet Auto-Updater ---")
    print(f"Current Config: Capital ₹{config.TOTAL_CAPITAL} | Risk ₹{config.MAX_RISK_INR}\n")
    
    # 1. Collect Data from AI Result
    try:
        symbol = input("Enter Stock Symbol (e.g., BEL): ").upper().strip()
        entry = float(input("Enter Entry Zone: "))
        value = float(input("Enter Value Zone (61.8% Retracement): "))
        sl = float(input("Enter Stop Loss Price: "))
        exit_lvl = float(input("Enter Exit Levels: "))

        # 2. Automated Calculations using config.py values
        risk_per_share = round(entry - sl, 2)
        qty = int(config.MAX_RISK_INR // risk_per_share) if risk_per_share > 0 else 0
        total_inv = round(qty * entry, 2)
    except ValueError:
        print("❌ Error: Please enter numeric values for prices.")
        return

    if not os.path.exists(config.TRADE_FILE):
        print(f"❌ Error: {config.TRADE_FILE} not found!")
        return

    # 3. Load and Update
    try:
        df = pd.read_excel(config.TRADE_FILE, sheet_name='Sheet1')
        df.columns = [str(c).strip() for c in df.columns]

        # Prepare the new data row
        new_data = {
            'Share Name': symbol,
            'Portfolio Capital (₹)': config.TOTAL_CAPITAL,
            'Entry Zone': entry,
            'Value Zone (Nifty 24k)': value,
            'Stop Loss Price': sl,
            'Exit Levels': exit_lvl,
            'Max Risk per Trade (%)': round((config.MAX_RISK_INR / config.TOTAL_CAPITAL) * 100, 2),
            'Risk per Trade': config.MAX_RISK_INR,
            'Risk per Share': risk_per_share,
            'Quantity to Buy': qty,
            'Total Investment': total_inv
        }

        # Check if Symbol exists
        mask = df['Share Name'].astype(str).str.upper().str.strip() == symbol
        if mask.any():
            print(f"🔄 Updating existing research for {symbol}...")
            idx = df[mask].index[0]
            for col, val in new_data.items():
                if col in df.columns:
                    df.at[idx, col] = val
        else:
            print(f"➕ Adding new research entry for {symbol}...")
            # Handle Serial Numbering
            next_sr = df['Sr No'].max() + 1 if 'Sr No' in df.columns and not df.empty else 1
            new_data['Sr No'] = next_sr
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)

        # 4. Save using the Retry Logic
        save_with_retry(df, config.TRADE_FILE)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    update_trade_sheet()
    input("\nPress Enter to exit...")