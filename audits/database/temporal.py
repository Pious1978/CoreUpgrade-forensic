import datetime
from .base import BaseAudit
from .utils import DatabaseInspector

class TemporalAudit(BaseAudit):
    dependency_level = 3

    def run(self):
        cursor = self.cursor()
        tables = DatabaseInspector.get_tables(self.conn)

        def is_exchange_holiday(date_obj):
            # Exchange calendar holiday check (Weekends + Sample Exchange Holidays)
            holidays = {datetime.date(2026, 1, 26), datetime.date(2026, 8, 15)}
            return date_obj.weekday() >= 5 or date_obj in holidays

        for tbl in tables:
            if not DatabaseInspector.table_exists(self.conn, tbl):
                continue
            info = DatabaseInspector.get_table_info(self.conn, tbl)
            col_lower = {c.lower() for c in info.keys()}

            if "date" in col_lower:
                cursor.execute(f"SELECT MAX(Date) FROM {tbl};")
                max_date = cursor.fetchone()[0]
                self.log("Coverage", "PASS", "Latest Trading Date", f"Table '{tbl}' latest date: {max_date}")

                cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE Date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]';")
                malformed = cursor.fetchone()[0]
                if malformed > 0:
                    self.log("Data Quality", "FAIL", "Date Format Validation", f"Table '{tbl}' has {malformed} malformed dates.")
                else:
                    self.log("Data Quality", "PASS", "Date Format Validation", f"All dates valid in '{tbl}'.")

                cursor.execute(f"SELECT DISTINCT Date FROM {tbl} ORDER BY Date ASC;")
                dates = [row[0] for row in cursor.fetchall()]
                
                abnormal_gaps = 0
                for i in range(len(dates) - 1):
                    try:
                        d1 = datetime.datetime.strptime(dates[i], "%Y-%m-%d").date()
                        d2 = datetime.datetime.strptime(dates[i+1], "%Y-%m-%d").date()
                        
                        curr = d1 + datetime.timedelta(days=1)
                        business_days_missed = 0
                        while curr < d2:
                            if not is_exchange_holiday(curr):
                                business_days_missed += 1
                            curr += datetime.timedelta(days=1)

                        if business_days_missed > 0:
                            abnormal_gaps += 1
                    except ValueError:
                        continue

                if abnormal_gaps > 0:
                    self.log("Data Quality", "WARNING", "Historical Continuity", f"Table '{tbl}' contains {abnormal_gaps} trading calendar gaps.")
                else:
                    self.log("Data Quality", "PASS", "Historical Continuity", f"Table '{tbl}' trading continuity verified via exchange calendar.")

        if "prices" in tables:
            cursor.execute("SELECT COUNT(DISTINCT Symbol) FROM prices;")
            syms = cursor.fetchone()[0]
            expected = self.context.config["expected_symbol_count"]
            if syms < expected:
                self.log("Coverage", "WARNING", "Symbol Coverage", f"Symbol count ({syms}) below expected baseline ({expected}).")
            else:
                self.log("Coverage", "PASS", "Symbol Coverage", f"Symbol coverage verified ({syms}/{expected}).")
