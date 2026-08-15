import psutil
import os
from typing import Dict, Any

class HealthMonitor:
    """Monitors runtime system health metrics (CPU, Memory) during execution."""

    def __init__(self):
        self._process = psutil.Process(os.getpid())

    def check_resource_health(self, max_memory_mb: float = 2048.0) -> Dict[str, Any]:
        mem_info = self._process.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        cpu_percent = self._process.cpu_percent(interval=0.1)

        return {
            "memory_rss_mb": round(rss_mb, 2),
            "cpu_percent": cpu_percent,
            "memory_exceeded": rss_mb > max_memory_mb
        }
