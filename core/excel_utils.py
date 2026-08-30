"""
core/excel_utils.py

Graceful handling for writing to an Excel file that's currently open
(a real, recurring PermissionError on Windows when the target .xlsx is
open in Excel). Adapted from the real save_with_retry() pattern found
in Alpha1/Obsolete/research_analyst.py and reused again in
Alpha1/Obsolete/alpha_strategist.py - a repeated, valued habit across
the user's own tools, not a one-off idea.

Important difference from the original pattern: research_analyst.py
was an interactive, user-run tool, so blocking on input() to wait for
the file to be closed was fine. Master_Terminal.py and
Bear_Market_Scanner.py run as automated pipeline stages via
Pipeline_DAG_Executor.py's subprocess calls, with no human present -
an input() prompt there would hang the entire pipeline indefinitely
instead of just failing loudly, a worse outcome than the crash this is
meant to prevent. So this version retries automatically a few times
with a short delay, then falls back to a timestamped filename rather
than losing the data or blocking forever.

Without this, Master_Terminal.py and Bear_Market_Scanner.py would
simply crash with an unhandled PermissionError if their output file
happened to be open for review at the moment the nightly pipeline runs.
"""

import time
import os
from datetime import datetime


def save_excel_with_retry(df, file_path, max_retries=3, retry_delay=5, **to_excel_kwargs):
    """
    Writes a DataFrame to Excel. If the file is currently open elsewhere,
    retries automatically (no human interaction, safe for automated
    pipeline stages) a few times with a short delay. If it still can't
    write, saves to a timestamped fallback filename instead of losing
    the data or blocking indefinitely.
    """

    for attempt in range(1, max_retries + 1):
        try:
            df.to_excel(file_path, **to_excel_kwargs)
            print(f"[+] Saved: {file_path}")
            return file_path

        except PermissionError:
            print(f"[!] '{file_path}' appears to be open (attempt {attempt}/{max_retries}) - "
                  f"retrying in {retry_delay}s...")
            time.sleep(retry_delay)

        except Exception as e:
            print(f"[-] Unexpected error saving '{file_path}': {e}")
            return None

    base, ext = os.path.splitext(file_path)
    fallback_path = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    try:
        df.to_excel(fallback_path, **to_excel_kwargs)
        print(f"[!] Could not save to '{file_path}' after {max_retries} attempts "
              f"(still appears open) - saved to '{fallback_path}' instead so nothing is lost.")
        return fallback_path

    except Exception as e:
        print(f"[-] Fallback save also failed: {e}")
        return None