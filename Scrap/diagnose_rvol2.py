import sys
sys.path.insert(0, ".")
from core.Live_Price_Engine import LivePriceEngine
import yfinance as yf

ticker = "20MICRONS"
symbol = ticker + ".NS"

print(f"=== Raw yfinance 5-minute data for {symbol} ===")
df = yf.download(symbol, period="5d", interval="5m", progress=False)
print(f"Rows fetched: {len(df)}")
print()
print("Last 5 rows (raw, before any processing):")
print(df.tail(5))
print()

print(f"=== What get_live_quote() actually returns ===")
quote = LivePriceEngine.get_live_quote(ticker)
print(quote)
