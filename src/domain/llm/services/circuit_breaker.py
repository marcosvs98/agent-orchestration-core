from __future__ import annotations


from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import DomainValidationException


class CircuitBreaker:
    def __init__(
        self,
        redis_adapter: RedisAdapter,
        *,
        failure_threshold: int = 5,
        window_seconds: int = 60,
        silent_mode: bool = True,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.redis = redis_adapter
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.silent_mode = silent_mode
        self.tracer = tracer

    def _key(self, scope: str) -> str:
        return f"cb:llm:{scope}"

    async def ensure_closed(self, scope: str) -> None:
        with self.tracer.observe(
            as_type="guardrail",
            name="domain.llm.circuit_breaker.ensure_closed",
            input={"scope": scope},
        ) as ensure_handle:
            if self.silent_mode:
                try:
                    data = await self.redis.get(self._key(scope))
                    if data and data.get("state") == "open":
                            raise DomainValidationException(
                                message="llm_circuit_breaker_open"
                            )
                except Exception:
                    if ensure_handle:
                        ensure_handle.success(
                            output={"state": "closed", "swallowed": True}
                        )
                    return
                if ensure_handle:
                    ensure_handle.success(output={"state": "closed"})
            else:
                data = await self.redis.get(self._key(scope))
                if data and data.get("state") == "open":
                        raise DomainValidationException(
                            message="llm_circuit_breaker_open"
                        )
            if ensure_handle:
                ensure_handle.success(output={"state": "closed"})

    async def record_failure(self, scope: str) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.llm.circuit_breaker.record_failure",
            input={"scope": scope},
        ) as failure_handle:
            try:
                count = await self.redis.incr_with_ttl(
                    self._key(scope), self.window_seconds
                )
                transitioned = count >= self.failure_threshold
                if transitioned:
                    await self.redis.set(
                        self._key(scope),
                        {"state": "open"},
                        ttl=self.window_seconds,
                    )
                if failure_handle:
                    failure_handle.success(
                        output={"count": int(count), "transitioned": transitioned}
                    )
            except Exception as exc:
                if failure_handle:
                    failure_handle.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"status": "error"},
                    )
                if not self.silent_mode:
                    raise exc from exc

    async def record_success(self, scope: str) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.llm.circuit_breaker.record_success",
            input={"scope": scope},
        ) as success_handle:
            try:
                await self.redis.delete(self._key(scope))
                if success_handle:
                    success_handle.success(output={"state": "cleared"})
            except Exception as exc:
                if success_handle:
                    success_handle.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"status": "error"},
                    )
                if not self.silent_mode:
                    raise exc from exc
