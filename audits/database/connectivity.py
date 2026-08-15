import os
import sqlite3
import pathlib
from .base import BaseAudit

class DatabaseConnectivityAudit(BaseAudit):
    dependency_level = 1

    def run(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            self.log("File Health", "FAIL", "Connectivity", "Database file does not exist.")
            return None

        if not os.access(self.db_path, os.R_OK) or not os.access(self.db_path, os.W_OK):
            self.log("File Health", "FAIL", "Database Permissions", "Read/Write permissions incorrect.")
            return None

        try:
            conn = sqlite3.connect(self.db_path, timeout=2.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            cursor.execute("PRAGMA encoding;")
            encoding = cursor.fetchone()[0]
            cursor.execute("SELECT sqlite_version();")
            sqlite_ver = cursor.fetchone()[0]

            self.log("File Health", "PASS", "Database Metadata", f"SQLite v{sqlite_ver}, Encoding: {encoding}, Journal: {journal_mode}")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self.log("Integrity", "FAIL", "Lock Detection", "Database currently locked.")
            else:
                self.log("Integrity", "FAIL", "Connectivity", f"Operational error: {e}")
            return None
