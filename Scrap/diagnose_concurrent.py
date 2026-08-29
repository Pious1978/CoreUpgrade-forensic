import sys
sys.path.insert(0, ".")
from core.Live_Price_Engine import LivePriceEngine
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

tickers = ["20MICRONS", "ABSLAMC", "360ONE", "ACE", "ACUTAAS", "ADANIENT", "AARTIIND", "ABCAPITAL", "ADANIPOWER", "ADANIPORTS"]

def fetch_quote(ticker):
    start = time.time()
    quote = LivePriceEngine.get_live_quote(ticker)
    quote["latency"] = round(time.time() - start, 2)
    return ticker, quote

print("=== Fetching all 10 concurrently, exactly like Live_Execution_Monitor.py does ===")
quotes = {}
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_quote, t) for t in tickers]
    for f in as_completed(futures):
        ticker, quote = f.result()
        quotes[ticker] = quote

for t in tickers:
    q = quotes.get(t, {})
    print(f"{t:12} -> rvol={q.get('rvol')}, ltp={q.get('ltp')}, status={q.get('status')}, latency={q.get('latency')}")
