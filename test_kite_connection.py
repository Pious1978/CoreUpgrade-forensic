"""
test_kite_connection.py

Real, direct security note: this script never contains your actual
api_key/api_secret. It reads them from a local .env file, which is
already listed in .gitignore - git will refuse to track it, so it
stays on your machine only and is never pushed to the public
CoreUpgrade-forensic repo, and Claude never sees its real content.

Setup, one-time only:
1. Copy .env.example to a new file named exactly ".env"
   (PowerShell: Copy-Item .env.example .env)
2. Open .env and replace the two placeholder values with your real
   Kite Connect API key and secret.
3. pip install python-dotenv kiteconnect --break-system-packages
4. Run this script: python test_kite_connection.py
"""

import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

api_key = os.getenv("KITE_API_KEY")
api_secret = os.getenv("KITE_API_SECRET")

if not api_key or api_key == "your_api_key_here":
    print("[!] KITE_API_KEY not set - copy .env.example to .env and fill in your real values.")
    exit(1)

kite = KiteConnect(api_key=api_key)

print("Open this URL in your browser and log in with your Zerodha credentials:")
print(kite.login_url())
print()

request_token = input("Paste the request_token from the redirect URL: ").strip()

data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])

print()
print("[+] Connected successfully. Fetching a real, live quote for RELIANCE...")

quote = kite.quote("NSE:RELIANCE")
print(quote)