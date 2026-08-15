import os
import hashlib
import platform
import sys
import ssl
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    python_version: str = field(default_factory=platform.python_version)
    os_platform: str = field(default_factory=platform.system)
    kernel_version: str = field(default_factory=platform.release)
    architecture: str = field(default_factory=platform.machine)
    processor: str = field(default_factory=platform.processor)
    compiler_version: str = field(default_factory=platform.python_compiler)
    glibc_version: str = field(default_factory=lambda: " ".join(platform.libc_ver()))
    openssl_version: str = field(default_factory=lambda: getattr(ssl, "OPENSSL_VERSION", "unknown"))
    serializer_version: str = "1.0.0"
    execution_engine_version: str = "2.4.0"
    manifest_schema: str = "v2"
    hash_algorithm: str = "sha256"
    cryptography_version: str = field(default_factory=lambda: getattr(sys.modules.get("cryptography", None), "__version__", "unknown"))
    numpy_version: str = field(default_factory=lambda: getattr(sys.modules.get("numpy", None), "__version__", "not_installed"))
    os_release_hash: str = field(default_factory=lambda: EnvironmentFingerprint._compute_file_hash("/etc/os-release"))
    # SEC-010: Supply chain lock dependency attestation
    dependency_lock_hash: str = field(default_factory=lambda: EnvironmentFingerprint._compute_file_hash("/opt/trading-engine/requirements.lock"))

    @staticmethod
    def _compute_file_hash(path: str) -> str:
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass
        return "unavailable"

    def compute_hash(self) -> str:
        raw = (
            f"{self.python_version}:{self.os_platform}:{self.kernel_version}:{self.architecture}:"
            f"{self.processor}:{self.compiler_version}:{self.glibc_version}:{self.openssl_version}:"
            f"{self.serializer_version}:{self.execution_engine_version}:{self.manifest_schema}:"
            f"{self.hash_algorithm}:{self.cryptography_version}:{self.numpy_version}:"
            f"{self.os_release_hash}:{self.dependency_lock_hash}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()