import yfinance as yf

df = yf.download("RELIANCE.NS", period="1y", interval="1d")
print(df.tail())
print(len(df))