from .base import BaseAudit
from .utils import DatabaseInspector

class DataQualityAudit(BaseAudit):
    dependency_level = 3

    def run(self):
        cursor = self.cursor()
        tables = DatabaseInspector.get_tables(self.conn)

        for tbl in tables:
            if not DatabaseInspector.table_exists(self.conn, tbl):
                continue
            info = DatabaseInspector.get_table_info(self.conn, tbl)
            col_names = set(info.keys())
            col_lower = {c.lower() for c in col_names}

            for col in ["Close", "Open", "Volume", "Symbol", "Date", "High", "Low"]:
                if col in col_names:
                    cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE \"{col}\" IS NULL;")
                    nulls = cursor.fetchone()[0]
                    if nulls > 0:
                        self.log("Data Quality", "WARNING", "Null Value Audit", f"Table '{tbl}' column '{col}' has {nulls:,} NULLs.")
                    else:
                        self.log("Data Quality", "PASS", "Null Value Audit", f"Table '{tbl}' column '{col}' has 0 NULLs.")

            if tbl == "prices" and {"Close", "Open", "High", "Low", "Volume"}.issubset(col_names):
                cursor.execute("SELECT COUNT(*) FROM prices WHERE Volume < 0 OR Close <= 0 OR Open <= 0 OR High < Low;")
                invalids = cursor.fetchone()[0]
                if invalids > 0:
                    self.log("Data Quality", "FAIL", "Invalid Values", f"Found {invalids} invalid price/volume records in prices.")
                else:
                    self.log("Data Quality", "PASS", "Invalid Values", "No invalid bounds in prices.")

            if "symbol" in col_lower and "date" in col_lower:
                cursor.execute(f"SELECT Symbol, Date, COUNT(*) as cnt FROM {tbl} GROUP BY Symbol, Date HAVING cnt > 1;")
                dups = cursor.fetchall()
                if dups:
                    syms = len(set(d[0] for d in dups))
                    dates = len(set(d[1] for d in dups))
                    total = sum(d[2] - 1 for d in dups)
                    self.log("Data Quality", "FAIL", "Duplicate Records", f"Found {total} duplicates in '{tbl}' ({syms} symbols, {dates} dates).")
                else:
                    self.log("Data Quality", "PASS", "Duplicate Records", f"No duplicates in '{tbl}'.")
