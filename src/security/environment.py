from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

class HardenedEnvironmentAttestation:
    """
    Runtime platform security measurements.
    Fail-closed philosophy: missing/unreadable measurements are represented as UNVERIFIED
    and rejected by assert_secure_boundary().
    """

    SECURE_BOOT_PATH = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ba-11d2-aa0d-00e098032b8c"

    @staticmethod
    def read_file(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
            return value or "UNVERIFIED"
        except Exception:
            return "UNVERIFIED"

    @staticmethod
    def hash_file(path: str) -> str:
        try:
            with open(path, "rb") as handle:
                data = handle.read()
            if not data:
                return "UNVERIFIED"
            return hashlib.sha384(data).hexdigest()
        except Exception:
            return "UNVERIFIED"

    @classmethod
    def secure_boot_state(cls) -> str:
        try:
            with open(cls.SECURE_BOOT_PATH, "rb") as handle:
                value = handle.read()

            if len(value) < 5:
                return "UNVERIFIED"

            secure_boot_value = value[4]

            if secure_boot_value == 1:
                return "ENABLED"
            if secure_boot_value == 0:
                return "DISABLED"

            return "UNVERIFIED"
        except Exception:
            return "UNVERIFIED"

@dataclass(frozen=True, slots=True)
class HardenedEnvironmentState:
    ptrace_scope: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.read_file("/proc/sys/kernel/yama/ptrace_scope")
    )
    lockdown_mode: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.read_file("/sys/kernel/security/lockdown")
    )
    secure_boot: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.secure_boot_state()
    )
    container_digest: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.read_file("/etc/podinfo/image_digest")
    )
    sbom_hash: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.hash_file("/etc/trading-engine/sbom.json")
    )
    slsa_hash: str = field(
        default_factory=lambda: HardenedEnvironmentAttestation.hash_file("/etc/trading-engine/slsa.intoto.jsonl")
    )

    def assert_secure_boundary(self) -> bool:
        if self.ptrace_scope not in ("2", "3"):
            raise RuntimeError("CRITICAL SECURITY ERROR: ptrace protection is insufficient.")

        lockdown = self.lockdown_mode.lower()
        if "integrity" not in lockdown and "confidentiality" not in lockdown:
            raise RuntimeError("CRITICAL SECURITY ERROR: Kernel lockdown unavailable.")

        if self.secure_boot != "ENABLED":
            raise RuntimeError("CRITICAL SECURITY ERROR: UEFI Secure Boot is not enabled.")

        if self.container_digest == "UNVERIFIED":
            raise RuntimeError("CRITICAL SECURITY ERROR: Container identity unavailable.")

        if self.sbom_hash == "UNVERIFIED":
            raise RuntimeError("CRITICAL SECURITY ERROR: SBOM verification unavailable.")

        if self.slsa_hash == "UNVERIFIED":
            raise RuntimeError("CRITICAL SECURITY ERROR: SLSA provenance unavailable.")

        return True