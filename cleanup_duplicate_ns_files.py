import os

cache_dir = "parquet_cache"
files = set(os.listdir(cache_dir))

ns_files = [f for f in files if f.endswith(".NS.parquet")]

print(f"Found {len(ns_files)} .NS.parquet files.")
print()

safe_to_delete = []
unsafe = []

for ns_file in ns_files:
    ticker = ns_file.replace(".NS.parquet", "")
    plain_file = f"{ticker}.parquet"

    if plain_file in files:
        safe_to_delete.append(ns_file)
    else:
        unsafe.append(ns_file)

print(f"Safe to delete (proper replacement confirmed present): {len(safe_to_delete)}")
print(f"UNSAFE - no proper replacement found, would lose data: {len(unsafe)}")

if unsafe:
    print()
    print("!!! STOPPING - these have no safe replacement, not deleting anything:")
    for f in unsafe:
        print(f"  {f}")
else:
    print()
    print("All .NS.parquet files have a confirmed, proper replacement.")
    print("Deleting now...")
    for f in safe_to_delete:
        os.remove(os.path.join(cache_dir, f))
    print(f"[+] Deleted {len(safe_to_delete)} redundant .NS.parquet files.")
    print(f"[+] All {len(safe_to_delete)} corresponding proper TICKER.parquet files remain untouched.")
