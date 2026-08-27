import random

class LatencyEngine:
    def __init__(self, fixed_delay_ms: int = 50, jitter_ms: int = 10):
        self.fixed_delay_ms = fixed_delay_ms
        self.jitter_ms = jitter_ms

    def compute_delay(self) -> int:
        jitter = random.randint(-self.jitter_ms, self.jitter_ms)
        return max(0, self.fixed_delay_ms + jitter)
