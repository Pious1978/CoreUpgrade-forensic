import sqlite3

class DatabaseInspector:
    @staticmethod
    def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
        return cursor.fetchone() is not None

    @staticmethod
    def get_tables(conn: sqlite3.Connection) -> list:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def get_table_info(conn: sqlite3.Connection, table_name: str) -> dict:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {row[1]: {"cid": row[0], "type": row[2].upper(), "notnull": row[3], "dflt": row[4], "pk": row[5]} for row in cursor.fetchall()}

    @staticmethod
    def count_rows(conn: sqlite3.Connection, table_name: str) -> int:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        return cursor.fetchone()[0]
