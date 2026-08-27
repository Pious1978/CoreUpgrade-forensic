# research/certification/theorems/theorem_performance_001.py
import time
import numpy as np

class PerformanceTheorem:
    id = "THEOREM-PERFORMANCE-001"
    MAX_OVERHEAD_PCT = 5.0
    
    @classmethod
    def verify(cls, raw_fn, tracked_fn, iterations=30) -> dict:
        raw_times = []
        tracked_times = []
        
        # Warmup
        raw_fn()
        tracked_fn()
        
        for _ in range(iterations):
            t0 = time.perf_counter()
            raw_fn()
            raw_times.append(time.perf_counter() - t0)
            
            t1 = time.perf_counter()
            tracked_fn()
            tracked_times.append(time.perf_counter() - t1)
            
        raw_p95 = np.percentile(raw_times, 95)
        tracked_p95 = np.percentile(tracked_times, 95)
        
        overhead_pct = ((tracked_p95 - raw_p95) / raw_p95) * 100 if raw_p95 > 0 else 0
        
        passed = overhead_pct <= cls.MAX_OVERHEAD_PCT
        
        return {
            "certified": passed,
            "metrics": {
                "raw_p95_ms": raw_p95 * 1000,
                "tracked_p95_ms": tracked_p95 * 1000,
                "overhead_pct": overhead_pct
            }
        }
