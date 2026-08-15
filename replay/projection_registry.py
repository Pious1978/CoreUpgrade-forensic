from typing import List, Tuple

from replay.models import Projection


class ProjectionRegistry:
    """Maintains a collection of active projections listening to the replay stream."""

    def __init__(self) -> None:
        self._projections: List[Projection] = []

    def register(self, projection: Projection) -> None:
        """Wires a new read-model projection into the event broadcast."""
        self._projections.append(projection)

    def projections(self) -> Tuple[Projection, ...]:
        """Returns an immutable tuple of registered projections."""
        return tuple(self._projections)
