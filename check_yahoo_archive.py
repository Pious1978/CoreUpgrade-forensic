import os

archive_dir = "parquet_cache_archive_yahoo"
if not os.path.exists(archive_dir):
    print(f"Archive directory {archive_dir} does not exist at all")
else:
    exists = os.path.exists(os.path.join(archive_dir, "BANKBEES.NS.parquet"))
    print(f"BANKBEES.NS.parquet exists in archive: {exists}")
    total = len([f for f in os.listdir(archive_dir) if f.endswith(".parquet")])
    print(f"Total files in archive: {total}")
