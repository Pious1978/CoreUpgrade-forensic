from abc import ABC, abstractmethod
import random


class RetryPolicy(ABC):
    """Abstract strategy interface for audit retry backoff calculation."""

    @abstractmethod
    def next_delay(self, attempt_number: int) -> float:
        pass


class ExponentialBackoffPolicy(RetryPolicy):
    """Calculates jittered exponential backoff delays."""

    def __init__(self, base: float = 0.25, multiplier: float = 2.0, max_delay: float = 30.0):
        self.base = base
        self.multiplier = multiplier
        self.max_delay = max_delay

    def next_delay(self, attempt_number: int) -> float:
        raw = min(self.max_delay, self.base * (self.multiplier ** (attempt_number - 1)))
        return raw * random.uniform(0.8, 1.2)  # Bounded proportional random jitter
