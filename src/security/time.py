import time
import hashlib
import subprocess

class TrustedTimeProvider:
    """
    SEC-009: Prevent system clock manipulation from bypassing certificate expiration.
    """
    @classmethod
    def get_trusted_utc_time(cls) -> float:
        # In institutional setups, this queries a hardware PTP clock or an authenticated NTP server via chronyc
        try:
            # Query chrony tracking for system clock synchronization status
            result = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, check=True, timeout=1.0)
            if "Leap status     : Normal" not in result.stdout:
                raise RuntimeError("Time synchronization is not in Normal state.")
            return time.time()
        except Exception as e:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Trusted time source verification failed: {str(e)}")

    @classmethod
    def get_trusted_time_hash(cls, trusted_time: float) -> str:
        payload = f"trusted_utc:{trusted_time:.6f}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()