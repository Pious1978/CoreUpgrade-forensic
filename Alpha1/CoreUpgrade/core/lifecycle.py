class LifecycleHooks:
    """Extension points for lifecycle event hooks during framework execution."""

    def before_all(self, context) -> None:
        pass

    def before_module(self, module_name: str, context) -> None:
        pass

    def after_module(self, module_name: str, results: list, context) -> None:
        pass

    def after_all(self, context, report) -> None:
        pass

    def on_failure(self, module_name: str, error: Exception, context) -> None:
        pass

    def on_retry(self, module_name: str, attempt: int, error: Exception) -> None:
        pass

    def on_timeout(self, module_name: str, context) -> None:
        pass
