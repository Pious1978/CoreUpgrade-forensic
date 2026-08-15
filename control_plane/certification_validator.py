"""
Certification Validator

Performs structural precondition checks on the incoming AuditRunResult
before it is evaluated by the CertificationEngine, maintaining a strict 
boundary between malformed evidence (ValidationException) and policy rejections.
"""

import re
from core.audit_run_result import AuditRunResult
from core.audit_result import AuditResult
from core.artifact_envelope import AuditArtifactEnvelope


class ValidationException(Exception):
    """Raised when an audit run result fails pre-certification structural validation."""
    pass


class CertificationValidator:

    _SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
    _REQUIRED_METADATA_KEYS = {
        "run_id",
        "scheduler_version",
        "started_at",
        "completed_at",
        "policy_version"
    }

    def __init__(self, require_fingerprint: bool = True):
        self.require_fingerprint = require_fingerprint

    def validate(self, audit_run_result: AuditRunResult) -> AuditRunResult:
        """
        Validates structural integrity, count consistency, metadata completeness, 
        and explicit type contracts on an AuditRunResult prior to policy evaluation.
        
        Returns the validated AuditRunResult to support a fluent pipeline.
        Raises ValidationException if any structural precondition fails.
        """
        if audit_run_result is None:
            raise ValidationException("Validation failed: AuditRunResult is None.")

        # 1. Explicit Attribute Access on AuditRunResult
        run_fingerprint = audit_run_result.run_fingerprint
        execution_results = audit_run_result.execution_results
        executed_gate_count = audit_run_result.executed_gate_count
        registered_gate_count = audit_run_result.registered_gate_count
        metadata = audit_run_result.metadata

        # 2. Gate Count Integrity & Non-Negative Validation
        if registered_gate_count < 0:
            raise ValidationException(
                "Validation failed: registered_gate_count cannot be negative."
            )
        if executed_gate_count < 0:
            raise ValidationException(
                "Validation failed: executed_gate_count cannot be negative."
            )
        if len(execution_results) != executed_gate_count:
            raise ValidationException(
                "Validation failed: execution_results length does not match executed_gate_count."
            )

        # 3. Cryptographic Fingerprint Validation
        if self.require_fingerprint:
            if not run_fingerprint:
                raise ValidationException(
                    "Validation failed: AuditRunResult missing required run_fingerprint."
                )
            if not isinstance(run_fingerprint, str):
                raise ValidationException(
                    "Validation failed: run_fingerprint must be a string."
                )
            if not self._SHA256_PATTERN.fullmatch(run_fingerprint):
                raise ValidationException(
                    "Validation failed: run_fingerprint is not a valid SHA-256 digest."
                )

        # 4. Execution Results Structure & Explicit AuditResult Type Contracts
        if not isinstance(execution_results, (list, tuple)):
            raise ValidationException(
                "Validation failed: execution_results must be a list or tuple."
            )

        for idx, result in enumerate(execution_results):
            if not isinstance(result, AuditResult):
                raise ValidationException(
                    f"Validation failed: Execution result at index {idx} is not a valid AuditResult instance."
                )

            status = result.status
            artifacts = result.artifacts

            if status is None:
                raise ValidationException(
                    f"Validation failed: Execution result at index {idx} is missing a 'status' attribute."
                )

            if status == "PASS":
                if artifacts is None:
                    raise ValidationException(
                        f"Validation failed: Passing gate at index {idx} contains null artifact payloads."
                    )
                if not isinstance(artifacts, (list, tuple)):
                    raise ValidationException(
                        f"Validation failed: artifacts at index {idx} must be a list or tuple."
                    )
                
                # Enforce that every artifact inside the container is an immutable envelope
                for artifact in artifacts:
                    if not isinstance(artifact, AuditArtifactEnvelope):
                        raise ValidationException(
                            f"Validation failed: Artifact at index {idx} is not a valid AuditArtifactEnvelope instance."
                        )

        # 5. Metadata Integrity & Required Manifest Key Validation
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValidationException(
                    "Validation failed: AuditRunResult metadata must be a dictionary container."
                )
            missing_keys = self._REQUIRED_METADATA_KEYS - metadata.keys()
            if missing_keys:
                raise ValidationException(
                    f"Validation failed: AuditRunResult metadata is missing required manifest keys: {sorted(missing_keys)}"
                )

        return audit_run_result
