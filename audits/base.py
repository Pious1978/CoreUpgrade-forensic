#!/usr/bin/env python3
"""
audits/base.py

Core audit execution framework.

Provides:
- AuditResult aggregation
- Execution lifecycle
- Exception isolation
- Finding propagation
- Audit telemetry
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from audits.findings import Finding, Severity


class AuditStatus(str, Enum):

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass
class AuditResult:

    audit_name: str

    status: AuditStatus = AuditStatus.PASS

    findings: list[Finding] = field(default_factory=list)

    metrics: dict[str, Any] = field(default_factory=dict)

    details: list[str] = field(default_factory=list)

    execution_time_ms: float = 0.0

    timestamp: datetime = field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    run_id: Optional[str] = None

    component: Optional[str] = None


    def add_finding(
        self,
        finding: Finding
    ) -> None:

        if not finding.run_id:
            finding.run_id = self.run_id

        if not finding.component:
            finding.component = self.component

        self.findings.append(finding)

        self._update_status(
            finding.severity
        )


    def _update_status(
        self,
        severity: Severity
    ):

        if severity == Severity.CRITICAL:
            self.status = AuditStatus.FAIL

        elif severity == Severity.HIGH:
            self.status = AuditStatus.FAIL

        elif severity == Severity.MEDIUM:

            if self.status == AuditStatus.PASS:
                self.status = AuditStatus.WARN

        elif severity == Severity.LOW:

            if self.status == AuditStatus.PASS:
                self.status = AuditStatus.WARN


    @property
    def has_failures(self):

        return self.status in (
            AuditStatus.FAIL,
            AuditStatus.ERROR
        )


    @property
    def finding_summary(self):

        summary = {
            "CRITICAL":0,
            "HIGH":0,
            "MEDIUM":0,
            "LOW":0,
            "INFO":0
        }

        for finding in self.findings:
            summary[
                finding.severity.value
            ] += 1

        return summary


    def to_dict(self):

        return {

            "audit_name":
                self.audit_name,

            "status":
                self.status.value,

            "timestamp":
                self.timestamp.isoformat(),

            "run_id":
                self.run_id,

            "component":
                self.component,

            "execution_time_ms":
                self.execution_time_ms,

            "metrics":
                self.metrics,

            "details":
                self.details,

            "finding_summary":
                self.finding_summary,

            "finding_count":
                len(self.findings),

            "findings":
                [
                    f.to_dict()
                    for f in self.findings
                ]
        }



class BaseAudit(ABC):


    def __init__(
        self,
        config: dict[str,Any]
    ):

        self.config = config

        self.name = (
            self.__class__.__name__
        )

        self.component = (
            self.name.lower()
        )


    @abstractmethod
    def run_checks(
        self,
        context: Any
    ) -> AuditResult:

        pass



    def execute(
        self,
        context: Any
    ) -> AuditResult:


        start = datetime.now(
            timezone.utc
        )


        run_id = getattr(
            context,
            "run_id",
            None
        )


        result = AuditResult(
            audit_name=self.name,
            run_id=run_id,
            component=self.component
        )


        try:

            output = self.run_checks(
                context
            )


            if isinstance(
                output,
                AuditResult
            ):
                result = output


            result.run_id = (
                result.run_id
                or run_id
            )

            result.component = (
                result.component
                or self.component
            )


        except Exception as exc:


            result.status = (
                AuditStatus.ERROR
            )


            result.add_finding(

                Finding(

                    severity=
                    Severity.CRITICAL,

                    category=
                    self.name,

                    metric=
                    "audit.execution.error",

                    actual=
                    str(exc),

                    expected=
                    "No execution errors",

                    message=
                    f"Audit execution failed: {exc}",

                    recommendation=
                    "Review logs and resolve underlying issue.",

                    component=
                    self.component,

                    run_id=
                    run_id,

                    tags=[
                        "AUDIT_FAILURE"
                    ],

                    exception=
                    str(exc)
                )
            )


        duration = (
            datetime.now(timezone.utc)
            -
            start
        ).total_seconds()*1000


        result.execution_time_ms = round(
            duration,
            2
        )


        return result
