"""
Gate Registry

Centralizes plugin discovery and registration to decouple audit plugins
from the root execution script.
"""

from audits.plugin_gate2 import Gate2Plugin
from audits.plugin_gate3 import Gate3Plugin
from audits.plugin_gate4 import Gate4Plugin
from audits.plugin_gate5 import Gate5Plugin
from audits.plugin_gate6 import Gate6Plugin
from audits.plugin_gate7 import Gate7Plugin


def load_registered_gates():
    """
    Returns an ordered list of instantiated audit gates for the certification pipeline.
    """
    return [
        Gate2Plugin(),
        Gate3Plugin(),
        Gate4Plugin(),
        Gate5Plugin(),
        Gate6Plugin(),
        Gate7Plugin()
    ]
