import time
import sqlite3
import pathlib
import concurrent.futures
from .base import BaseAudit, AuditResult
from .utils import DatabaseInspector

class PerformanceAudit(BaseAudit):
    dependency_level = 3

    def run(self):
        cursor = self.cursor()
        tables = DatabaseInspector.get_tables(self.conn)

        if "prices" in tables:
            workloads = {
                "POINT_LOOKUP": "SELECT * FROM prices WHERE Symbol = 'TEST' ORDER BY Date DESC LIMIT 252;",
                "GROUP_BY_SYMBOL": "SELECT Symbol, COUNT(*), AVG(Close) FROM prices GROUP BY Symbol LIMIT 50;",
                "SCAN_TOP_RS": "SELECT * FROM prices ORDER BY Close DESC LIMIT 100;"
            }

            for name, query in workloads.items():
                try:
                    start = time.time()
                    cursor.execute(query)
                    cursor.fetchall()
                    lat = (time.time() - start) * 1000
                    if lat > 150:
                        self.log("Performance", "WARNING", f"Benchmark: {name}", f"Query latency high ({lat:.2f}ms).")
                    else:
                        self.log("Performance", "PASS", f"Benchmark: {name}", f"Query latency optimal ({lat:.2f}ms).")
                except sqlite3.Error as e:
                    self.log("Performance", "WARNING", f"Benchmark: {name}", f"Benchmark skipped/failed: {e}")

        if "prices" in tables:
            cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM prices WHERE Symbol = 'RELIANCE' AND Date = '2026-07-30';")
            plan_text = " ".join([str(r) for r in cursor.fetchall()]).lower()
            if "scan table prices" in plan_text and "using index" not in plan_text and "search table" not in plan_text:
                self.log("Performance", "WARNING", "Missing Index Detection", "Full table scan detected on prices. Missing index.")
            else:
                self.log("Performance", "PASS", "Missing Index Detection", "Index utilization optimal.")

def run_stress_test(config, context):
    db_target = config["databases"][0]
    if not pathlib.Path(db_target).exists():
        return

    def reader():
        try:
            c = sqlite3.connect(db_target, timeout=5.0)
            c.execute("SELECT COUNT(*) FROM sqlite_master;")
            c.close()
            return True
        except Exception:
            return False

    def writer():
        try:
            c = sqlite3.connect(db_target, timeout=5.0)
            c.execute("SAVEPOINT stress_test;")
            c.execute("CREATE TEMP TABLE IF NOT EXISTS stress_log (id INTEGER);")
            c.execute("INSERT INTO stress_log VALUES (1);")
            c.commit()
            c.close()
            return True
        except Exception:
            return False

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(reader) for _ in range(20)] + [executor.submit(writer) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            if not f.result():
                failures += 1

    if failures > 0:
        context.add_result(AuditResult("Performance", "WARNING", "Connection Stress Test", db_target, f"Encountered {failures} concurrency failures."))
    else:
        context.add_result(AuditResult("Performance", "PASS", "Connection Stress Test", db_target, "Completed 25 concurrent reader/writer connections with 0 failures."))
