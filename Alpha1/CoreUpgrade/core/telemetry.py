import time
import psutil
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class ModuleTelemetry:
    module_name: str
    duration_seconds: float = 0.0
    cpu_time_seconds: float = 0.0
    memory_delta_mb: float = 0.0
    retries: int = 0
    timeouts: int = 0
    exceptions: List[str] = field(default_factory=list)
    skipped: bool = False
    execution_order: int = 0

class TelemetryCollector:
    """Collects precise performance, timing, CPU time, and memory consumption telemetry."""

    def __init__(self):
        self.metrics: Dict[str, ModuleTelemetry] = {}
        self._process = psutil.Process(os.getpid())

    def start_module(self, name: str) -> Tuple[float, Any, int]:
        if name not in self.metrics:
            self.metrics[name] = ModuleTelemetry(module_name=name)
        
        cpu_start = self._process.cpu_times()
        mem_start = self._process.memory_info().rss
        perf_start = time.perf_counter()
        
        return perf_start, cpu_start, mem_start

    def end_module(self, name: str, start_tuple: Tuple[float, Any, int], retries: int = 0, exception: str = None, skipped: bool = False):
        perf_start, cpu_start, mem_start = start_tuple
        duration = time.perf_counter() - perf_start
        
        cpu_end = self._process.cpu_times()
        cpu_time = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
        
        mem_end = self._process.memory_info().rss
        mem_delta_mb = (mem_end - mem_start) / (1024 * 1024)

        m = self.metrics[name]
        m.duration_seconds = duration
        m.cpu_time_seconds = cpu_time
        m.memory_delta_mb = mem_delta_mb
        m.retries = retries
        m.skipped = skipped
        if exception:
            m.exceptions.append(exception)
