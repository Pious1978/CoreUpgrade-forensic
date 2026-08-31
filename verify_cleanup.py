import os
files = os.listdir("parquet_cache")
remaining_ns = [f for f in files if f.endswith(".NS.parquet")]
print(f"Remaining .NS.parquet files: {len(remaining_ns)} (should be 0)")
print(f"Total files in parquet_cache now: {len(files)}")

for t in ["ABSLAMC", "ADANIENSOL"]:
    plain_name = t + ".parquet"
    ns_name = t + ".NS.parquet"
    print(f"{t}.parquet still present: {plain_name in files}")
    print(f"{t}.NS.parquet gone: {ns_name not in files}")
