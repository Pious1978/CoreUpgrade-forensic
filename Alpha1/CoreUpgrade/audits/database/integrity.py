import sqlite3
from .base import BaseAudit
from .utils import DatabaseInspector

class IntegrityAudit(BaseAudit):
    dependency_level = 2

    def run(self):
        cursor = self.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()[0]
        if res == "ok":
            self.log("Integrity", "PASS", "Database Integrity", "PRAGMA integrity_check passed (ok).")
        else:
            self.log("Integrity", "FAIL", "Database Integrity", f"Corruption detected: {res}")

        cursor.execute("PRAGMA foreign_key_check;")
        fk_violations = cursor.fetchall()
        if fk_violations:
            self.log("Integrity", "FAIL", "Foreign Key Audit", f"Foreign key violations found: {len(fk_violations)}")
        else:
            self.log("Integrity", "PASS", "Foreign Key Audit", "No foreign key violations detected.")

        tables = DatabaseInspector.get_tables(self.conn)
        for tbl in tables:
            info = DatabaseInspector.get_table_info(self.conn, tbl)
            pk_cols = [col for col, data in info.items() if data["pk"] > 0]
            if not pk_cols:
                self.log("Integrity", "WARNING", "Primary Key Validation", f"Table '{tbl}' has no Primary Key defined.")
                continue

            pk_str = ", ".join([f'"{c}"' for c in pk_cols])
            cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT {pk_str}) FROM {tbl};")
            total, distinct = cursor.fetchone()
            if total != distinct:
                self.log("Integrity", "FAIL", "Primary Key Validation", f"Table '{tbl}' has duplicate Primary Key entries.")
            else:
                self.log("Integrity", "PASS", "Primary Key Validation", f"Table '{tbl}' primary keys are unique.")
