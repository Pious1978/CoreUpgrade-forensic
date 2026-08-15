import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from core.logger import get_logger

logger = get_logger("evidence_validator")


class EvidenceValidator:
    """
    Cryptographic evidence verifier validating self-contained artifact packages
    against their embedded checksum registry (checksums.json).
    """

    def __init__(self, package_path: str):
        self.package_path = Path(package_path)

    def _compute_sha256(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify(self) -> Dict[str, Any]:
        checksum_file = self.package_path / "checksums.json"
        if not checksum_file.exists():
            logger.error("Missing checksums.json in evidence package", extra={"path": str(self.package_path)})
            return {"valid": False, "error": "Missing checksums.json registry", "tampered_files": []}

        try:
            with open(checksum_file, "r", encoding="utf-8") as f:
                expected_checksums: Dict[str, str] = json.load(f)
        except Exception as e:
            logger.error("Failed to parse checksums.json", extra={"error": str(e)})
            return {"valid": False, "error": f"Malformed checksum registry: {str(e)}", "tampered_files": []}

        tampered_files: List[str] = []
        missing_files: List[str] = []

        for rel_path, expected_hash in expected_checksums.items():
            target_file = self.package_path / rel_path
            if not target_file.exists():
                missing_files.append(rel_path)
                continue
            
            actual_hash = self._compute_sha256(target_file)
            if actual_hash != expected_hash:
                tampered_files.append(rel_path)

        is_valid = len(tampered_files) == 0 and len(missing_files) == 0
        
        logger.info(
            "Evidence package verification completed",
            extra={"valid": is_valid, "tampered_count": len(tampered_files), "missing_count": len(missing_files)}
        )

        return {
            "valid": is_valid,
            "tampered_files": tampered_files,
            "missing_files": missing_files
        }
