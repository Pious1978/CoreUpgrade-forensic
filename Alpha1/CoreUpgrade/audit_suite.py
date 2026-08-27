#!/usr/bin/env python3
"""
audit_suite.py
Master Audit Orchestrator. Coordinates multi-domain pipeline audits (Database, 
Market Data, Research, Risk, and Pipeline Flow) into a unified run cycle.
"""

import sys
import logging
import datetime

from core.audit_context import AuditContext
from audits.database.config import AUDIT_CONFIG
from database_audit import DatabaseAuditOrchestrator
from audits.database.exports import AuditExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AuditSuite")

class MasterAuditSuite:
    def __init__(self, config: dict):
        self.config = config
        self.context = AuditContext(config)

    def run_suite(self):
        logger.info("==================================================")
        logger.info("       STARTING MASTER INSTITUTIONAL AUDIT        ")
        logger.info("==================================================")
        
        start_time = datetime.datetime.now()

        # 1. Execute Database Audit Layer
        logger.info("[Step 1/6] Executing Database Audit Layer...")
        db_orchestrator = DatabaseAuditOrchestrator(self.config)
        db_orchestrator.run()

        # (Future steps: Market Data, Research, Risk, Pipeline Flow, Report Generator)

        duration = (datetime.datetime.now() - start_time).total_seconds()
        logger.info(f"Master audit suite completed in {duration:.2f} seconds.")

if __name__ == "__main__":
    suite = MasterAuditSuite(AUDIT_CONFIG)
    suite.run_suite()
