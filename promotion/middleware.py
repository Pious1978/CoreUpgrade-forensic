from abc import ABC, abstractmethod
from typing import Callable, Any, Awaitable, List
from .context import PromotionContext
from .result_types import PromotionResult
from .exceptions import PermissionDeniedError, AuthenticationError, FatalPromotionError, RetryablePromotionError

class PromotionMiddleware(ABC):
    order: int = 100

    async def before(self, source: Any, target_type: Any, context: PromotionContext) -> None:
        """Standardized pre-execution hook."""
        pass

    async def after(self, source: Any, target_type: Any, context: PromotionContext, result: PromotionResult) -> None:
        """Standardized post-execution hook."""
        pass

    @abstractmethod
    async def handle(self, source: Any, target_type: Any, context: PromotionContext, next_handler: Callable[..., Awaitable[PromotionResult]]) -> PromotionResult:
        pass

class ExceptionMiddleware(PromotionMiddleware):
    order = 1000
    async def handle(self, source: Any, target_type: Any, context: PromotionContext, next_handler: Callable[..., Awaitable[PromotionResult]]) -> PromotionResult:
        try:
            return await next_handler(source, target_type, context)
        except RetryablePromotionError:
            raise
        except Exception as e:
            if not isinstance(e, FatalPromotionError):
                raise FatalPromotionError(f"Wrapped fatal error: {e}") from e
            raise

class AuthenticationMiddleware(PromotionMiddleware):
    order = 10
    async def before(self, source: Any, target_type: Any, context: PromotionContext) -> None:
        if not context.actor:
            raise AuthenticationError("Authentication failed: Missing actor identity in PromotionContext.")

    async def handle(self, source: Any, target_type: Any, context: PromotionContext, next_handler: Callable[..., Awaitable[PromotionResult]]) -> PromotionResult:
        await self.before(source, target_type, context)
        result = await next_handler(source, target_type, context)
        await self.after(source, target_type, context, result)
        return result

class AuthorizationMiddleware(PromotionMiddleware):
    order = 20
    async def before(self, source: Any, target_type: Any, context: PromotionContext) -> None:
        scopes = context.permissions.scopes
        if scopes and "PROMOTE" not in scopes:
            raise PermissionDeniedError(f"Actor '{context.actor}' lacks required 'PROMOTE' permission scope.")

    async def handle(self, source: Any, target_type: Any, context: PromotionContext, next_handler: Callable[..., Awaitable[PromotionResult]]) -> PromotionResult:
        await self.before(source, target_type, context)
        result = await next_handler(source, target_type, context)
        await self.after(source, target_type, context, result)
        return result

class AsyncMiddlewarePipeline:
    def __init__(self, core_executor: Callable[..., Awaitable[PromotionResult]]) -> None:
        self.middlewares: List[PromotionMiddleware] = []
        self.core_executor = core_executor

    def use(self, middleware: PromotionMiddleware) -> "AsyncMiddlewarePipeline":
        self.middlewares.append(middleware)
        self.middlewares.sort(key=lambda x: x.order)
        return self

    async def execute(self, source: Any, target_type: Any, context: PromotionContext) -> PromotionResult:
        current = self.core_executor
        for mw in reversed(self.middlewares):
            h = current
            current = lambda s, t, c, mw=mw, next_h=h: mw.handle(s, t, c, next_h)
        return await current(source, target_type, context)
