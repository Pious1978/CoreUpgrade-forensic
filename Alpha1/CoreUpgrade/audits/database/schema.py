from .base import BaseAudit
from .utils import DatabaseInspector

class SchemaAudit(BaseAudit):
    dependency_level = 2

    def run(self):
        tables = DatabaseInspector.get_tables(self.conn)
        required = self.context.config["required_tables"].get(self.db_name, [])
        for tbl in required:
            if tbl in tables:
                self.log("Schema", "PASS", "Table Existence", f"Table '{tbl}' exists.")
            else:
                self.log("Schema", "FAIL", "Table Existence", f"Required table '{tbl}' missing.")

        expected = self.context.config["expected_schemas"].get(self.db_name, {})
        for tbl, spec in expected.items():
            if tbl in tables:
                actual_cols = DatabaseInspector.get_table_info(self.conn, tbl)
                expected_cols = spec["cols"]
                for col, exp_type in expected_cols.items():
                    if col not in actual_cols:
                        self.log("Schema", "FAIL", "Schema Drift", f"Column '{col}' missing from '{tbl}'.")
                    elif actual_cols[col]["type"] != exp_type.upper():
                        self.log("Schema", "WARNING", "Schema Drift", f"Type mismatch on '{tbl}.{col}': expected {exp_type}, got {actual_cols[col]['type']}")
                    else:
                        self.log("Schema", "PASS", "Schema Drift", f"Schema verified for '{tbl}.{col}'.")
