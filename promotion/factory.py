import inspect
from typing import Type, Any, Dict, get_type_hints
from enum import Enum
from .exceptions import DependencyError

class ServiceLifetime(Enum):
    SINGLETON = "SINGLETON"
    SCOPED = "SCOPED"
    TRANSIENT = "TRANSIENT"

class ServiceDescriptor:
    def __init__(self, implementation_type: Type[Any], lifetime: ServiceLifetime) -> None:
        self.implementation_type = implementation_type
        self.lifetime = lifetime

class PromotionFactory:
    """Enterprise DI container respecting scoped dictionary references without accidental overwrites."""
    def __init__(self) -> None:
        self._registry: Dict[Any, ServiceDescriptor] = {}
        self._singletons: Dict[Any, Any] = {}

    def register(self, service_type: Any, implementation_type: Type[Any], lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT) -> None:
        self._registry[service_type] = ServiceDescriptor(implementation_type, lifetime)

    def create(self, promoter_class: Type[Any], scope_container: Dict[Any, Any] = None) -> Any:
        if scope_container is None:
            scope_container = {}

        init_method = getattr(promoter_class, "__init__", None)
        if not init_method or init_method is object.__init__:
            return promoter_class()

        signature = inspect.signature(init_method)
        hints = get_type_hints(init_method)
        dependencies = {}

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue
            
            dep_type = hints.get(name) or name
            if dep_type in scope_container:
                dependencies[name] = scope_container[dep_type]
            elif name in scope_container:
                dependencies[name] = scope_container[name]
            elif dep_type in self._singletons:
                dependencies[name] = self._singletons[dep_type]
            elif name in self._singletons:
                dependencies[name] = self._singletons[name]
            elif dep_type in self._registry:
                desc = self._registry[dep_type]
                if desc.lifetime == ServiceLifetime.SINGLETON:
                    if dep_type not in self._singletons:
                        self._singletons[dep_type] = self.create(desc.implementation_type, scope_container)
                    dependencies[name] = self._singletons[dep_type]
                elif desc.lifetime == ServiceLifetime.SCOPED:
                    if dep_type not in scope_container:
                        scope_container[dep_type] = self.create(desc.implementation_type, scope_container)
                    dependencies[name] = scope_container[dep_type]
                else:
                    dependencies[name] = self.create(desc.implementation_type, scope_container)
            elif name in self._registry:
                desc = self._registry[name]
                if desc.lifetime == ServiceLifetime.SINGLETON:
                    if name not in self._singletons:
                        self._singletons[name] = self.create(desc.implementation_type, scope_container)
                    dependencies[name] = self._singletons[name]
                elif desc.lifetime == ServiceLifetime.SCOPED:
                    if name not in scope_container:
                        scope_container[name] = self.create(desc.implementation_type, scope_container)
                    dependencies[name] = scope_container[name]
                else:
                    dependencies[name] = self.create(desc.implementation_type, scope_container)
            elif parameter.default is inspect.Parameter.empty:
                raise DependencyError(f"Missing dependency '{name}' (type: {dep_type}) for '{promoter_class.__name__}'.")

        return promoter_class(**dependencies)
