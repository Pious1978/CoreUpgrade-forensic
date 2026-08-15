import importlib
import pkgutil
from typing import List

class PluginManager:
    """Manages plugin lifecycle, dynamic loading, and version compatibility checks."""

    def __init__(self, supported_framework_version: str = "2.0.0"):
        self.supported_version = supported_framework_version

    def load_plugins(self, package_names: List[str]) -> None:
        for pkg_name in package_names:
            try:
                pkg = importlib.import_module(pkg_name)
                for _, modname, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
                    importlib.import_module(modname)
            except ImportError:
                pass

    def validate_plugin_compatibility(self, plugin_version: str) -> bool:
        plugin_major = plugin_version.split(".")[0]
        framework_major = self.supported_version.split(".")[0]
        return plugin_major == framework_major
