class AuditResult:
    def __init__(self, category: str, severity: str, check_name: str, database: str, message: str):
        self.category = category
        self.severity = severity.upper()
        self.check_name = check_name
        self.database = database
        self.message = message

    def to_dict(self):
        return {
            "category": self.category,
            "severity": self.severity,
            "check": self.check_name,
            "database": self.database,
            "message": self.message
        }

class BaseAudit:
    dependency_level = 1  # 1: Connectivity, 2: Integrity/Schema, 3: Data/Performance

    def __init__(self, conn, db_name, context, db_path=None):
        self.conn = conn
        self.db_name = db_name
        self.context = context
        self.db_path = db_path

    def cursor(self):
        return self.conn.cursor()

    def log(self, category: str, severity: str, check_name: str, message: str):
        result = AuditResult(category, severity, check_name, self.db_name, message)
        self.context.add_result(result)
