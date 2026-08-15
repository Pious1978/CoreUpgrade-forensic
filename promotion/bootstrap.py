import importlib
import pkgutil
from . import implementations
from .graph import default_registry
from .health import PromotionHealthChecker
from .exceptions import CompatibilityError
from . import API_VERSION

def initialize_promotions(target_api_version: int = 2) -> None:
    if target_api_version != API_VERSION:
        raise CompatibilityError(f"Framework API version mismatch: Target expects API {target_api_version}, but engine is API {API_VERSION}.")

    package = implementations
    for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_name)
    
    default_registry.freeze()
    PromotionHealthChecker.verify(default_registry)
