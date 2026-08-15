import json
import csv
import logging

logger = logging.getLogger("DatabaseAudit")

class AuditExporter:
    @staticmethod
    def export(results: dict):
        # JSON
        with open("database_audit.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        
        # CSV
        with open("database_audit.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Severity", "Check", "Database", "Message"])
            for d in results["details"]:
                writer.writerow([d["category"], d["severity"], d["check"], d["database"], d["message"]])

        # Markdown
        with open("database_audit.md", "w", encoding="utf-8") as f:
            f.write(f"# Database Audit Report\n\n- **Timestamp:** {results['timestamp']}\n- **Database Score:** {results.get('database_score', 0)}%\n\n")
            f.write(f"### Summary\n- **Pass:** {results['pass']}\n- **Warning:** {results['warning']}\n- **Fail:** {results['fail']}\n\n")
            f.write("### Details\n| Category | Severity | Check | Database | Message |\n|---|---|---|---|---|\n")
            for d in results["details"]:
                f.write(f"| {d['category']} | {d['severity']} | {d['check']} | {d['database']} | {d['message']} |\n")

        # HTML
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <title>Database Audit Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
                h1 {{ color: #2c3e50; }}
                .score {{ font-size: 24px; font-weight: bold; color: #27ae60; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; }}
                th {{ background-color: #f4f6f7; }}
                .PASS {{ color: #27ae60; font-weight: bold; }}
                .WARNING {{ color: #d68910; font-weight: bold; }}
                .FAIL, .CRITICAL {{ color: #c0392b; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Database Audit Report</h1>
            <p><strong>Timestamp:</strong> {results['timestamp']}</p>
            <p>Database Score: <span class="score">{results.get('database_score', 0)}%</span></p>
            <h3>Summary</h3>
            <ul>
                <li>Pass: {results['pass']}</li>
                <li>Warning: {results['warning']}</li>
                <li>Fail: {results['fail']}</li>
            </ul>
            <h3>Audit Details</h3>
            <table>
                <tr><th>Category</th><th>Severity</th><th>Check</th><th>Database</th><th>Message</th></tr>
        """
        for d in results["details"]:
            html += f"<tr><td>{d['category']}</td><td class='{d['severity']}'>{d['severity']}</td><td>{d['check']}</td><td>{d['database']}</td><td>{d['message']}</td></tr>\n"
        html += "</table></body></html>"

        with open("database_audit.html", "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Exported database_audit.json, .csv, .md, and .html successfully.")
