from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timezone

@dataclass(frozen=True)
class StageMetric:
    stage_name: str
    duration_ms: float
    input_type: str
    output_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class PipelineTelemetry:
    def __init__(self):
        self._metrics: List[StageMetric] = []

    def record(self, stage_name: str, duration_ms: float, input_type: str, output_type: str):
        metric = StageMetric(
            stage_name=stage_name,
            duration_ms=round(duration_ms, 3),
            input_type=input_type,
            output_type=output_type
        )
        self._metrics.append(metric)

    @property
    def metrics(self) -> List[StageMetric]:
        return self._metrics
