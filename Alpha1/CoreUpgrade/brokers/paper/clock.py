import time
from abc import ABC, abstractmethod

class Clock(ABC):
    @abstractmethod
    def now_ms(self) -> int:
        pass

class SystemClock(Clock):
    def now_ms(self) -> int:
        return int(time.time() * 1000)
