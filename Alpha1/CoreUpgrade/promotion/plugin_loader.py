import importlib
from typing import List

class PluginLoader:
    """Dynamically discovers and loads external institutional promotion plugins."""

    @staticmethod
    def load_plugins(plugin_modules: List[str]) -> None:
        for mod in plugin_modules:
            importlib.import_module(mod)
