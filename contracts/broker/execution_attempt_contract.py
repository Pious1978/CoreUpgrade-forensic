from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionAttemptContract:
    attempt_id: str
    order_id: str
    attempt_number: int
    timestamp: int
    correlation_id: str

    def __post_init__(self):
        if self.attempt_number < 1:
            raise ValueError("Attempt number must be positive (>= 1)")
