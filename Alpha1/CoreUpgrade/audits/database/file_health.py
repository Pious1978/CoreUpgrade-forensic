import pathlib
from .base import BaseAudit

class FileHealthAudit(BaseAudit):
    dependency_level = 2

    def run(self):
        wal_path = pathlib.Path(f"{self.db_path}-wal")
        shm_path = pathlib.Path(f"{self.db_path}-shm")
        cursor = self.cursor()
        cursor.execute("PRAGMA journal_mode;")
        j_mode = cursor.fetchone()[0].lower()

        if j_mode == "wal":
            if not shm_path.exists():
                self.log("File Health", "WARNING", "WAL Health", "WAL mode active but missing .shm file.")
            elif wal_path.exists() and wal_path.stat().st_size > 100 * 1024 * 1024:
                self.log("File Health", "WARNING", "WAL Health", f"Huge WAL file detected ({wal_path.stat().st_size / (1024*1024):.1f} MB).")
            else:
                self.log("File Health", "PASS", "WAL Health", "WAL and SHM health optimal.")
        else:
            self.log("File Health", "PASS", "WAL Health", f"Non-WAL journal mode ({j_mode}).")

        cursor.execute("PRAGMA page_count;")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size;")
        page_size = cursor.fetchone()[0]
        cursor.execute("PRAGMA freelist_count;")
        free_pages = cursor.fetchone()[0]

        free_pct = (free_pages / page_count * 100) if page_count > 0 else 0.0
        max_free = self.context.config["thresholds"]["max_free_page_pct"]
        if free_pct > max_free:
            self.log("File Health", "WARNING", "Vacuum Recommendation", f"Database fragmented ({free_pct:.1f}% free). Recommended: VACUUM")
        else:
            self.log("File Health", "PASS", "Vacuum Recommendation", f"Database utilization healthy ({free_pct:.1f}% free).")
