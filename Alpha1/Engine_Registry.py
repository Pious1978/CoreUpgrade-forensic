"""
Engine_Registry.py
-------------------------------------------------------------------------
Dynamic Service Broker and Discoverable Execution Registry
"""
from typing import Callable, Dict
from Standard_Engine_Types import FeatureStore, EngineResult

class EngineRegistry:
    def __init__(self):
        self._registry: Dict[str, Callable[[FeatureStore], EngineResult]] = {}

    def register(self, engine_name: str, execution_pointer: Callable[[FeatureStore], EngineResult]):
        """Registers a scanning module service into the platform mapping tree."""
        self._registry[engine_name] = execution_pointer

    def execute_all(self, store: FeatureStore) -> Dict[str, EngineResult]:
        """Runs every discovered engine dynamically against the static FeatureStore context."""
        pipeline_outputs = {}
        for name, engine_fn in self._registry.items():
            try:
                pipeline_outputs[name] = engine_fn(store)
            except Exception as e:
                pipeline_outputs[name] = EngineResult(
                    engine_name=name, version="unknown", score=0.0, 
                    verdict="ERROR", confidence=0.0, metrics={}, commentary=f"Crash: {e}"
                )
        return pipeline_outputs