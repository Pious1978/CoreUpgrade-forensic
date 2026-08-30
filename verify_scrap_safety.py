import os

SCRAP_DIR = "Scrap"
SEARCH_DIRS = [".", "Alpha1"]  # root and Alpha1, excluding Scrap itself

scrap_files = os.listdir(SCRAP_DIR)

print(f"Checking {len(scrap_files)} files in Scrap/ against every reference in root and Alpha1...\n")

any_hits = False

for scrap_file in scrap_files:
    hits = []

    for search_dir in SEARCH_DIRS:
        for dirpath, dirnames, filenames in os.walk(search_dir):
            # Don't search inside Scrap itself, or hidden/venv dirs
            dirnames[:] = [d for d in dirnames if d not in ("Scrap", ".git", "__pycache__", "Obsolete")]

            for fname in filenames:
                if not fname.endswith((".py", ".txt")):
                    continue

                full_path = os.path.join(dirpath, fname)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue

                if scrap_file in content:
                    hits.append(full_path)

    if hits:
        any_hits = True
        print(f"[!] {scrap_file} is REFERENCED by:")
        for h in hits:
            print(f"      {h}")
        print()

if not any_hits:
    print("No references found anywhere in root or Alpha1 to any file in Scrap/.")
    print("The move is confirmed safe.")