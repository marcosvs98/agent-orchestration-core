from uuid import UUID
import contextlib

import json
import time

from pydantic import ValidationError
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.state_machine import ToolRunStatus, RunStatus
from domain.tools.ports.tool_executor import ToolExecutorPort
from domain.tools.ports.secret_resolver import SecretResolverPort
from domain.execution.schemas.events import ExecutionEventType
from domain.tools.schemas.http_result import HttpToolResult
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer
from exceptions.service_exceptions import DomainValidationException


class ToolOrchestrator:
    def __init__(
        self,
        repository: ExecutionRepository,
        executor: ToolExecutorPort,
        secret_resolver: SecretResolverPort,
        tracer: LangfuseRuntimeTracer | None = None,
    ) -> None:
        self.repository = repository
        self.executor = executor
        self.secret_resolver = secret_resolver
        self.tracer = tracer

    async def _resolve_headers(
        self, *, headers_config: dict
    ) -> tuple[dict[str, str], list[str]]:
        resolved: dict[str, str] = {}
        used_secret_refs: list[str] = []
        for key, value in (headers_config or {}).items():
            if isinstance(value, dict) and "secret_ref" in value:
                secret_ref = str(value["secret_ref"])
                secret_value = await self.secret_resolver.resolve(secret_ref=secret_ref)
                resolved[str(key)] = secret_value
                used_secret_refs.append(secret_ref)
                continue
            if isinstance(value, str):
                resolved[str(key)] = value
                continue
            raise DomainValidationException(message="invalid_tool_headers_config")
        return resolved, used_secret_refs

    async def execute_tool_run(self, *, tool_run_id: UUID) -> dict:
        tool_run = await self.repository.get_tool_run(tool_run_id)
        if tool_run is None:
            raise DomainValidationException(message="tool_run_not_found")

        tool_config = await self.repository.get_tool_config(tool_run.tool_config_id)
        if tool_config is None:
            raise DomainValidationException(message="tool_config_not_found")

        config: dict = tool_config.config or {}
        url = config.get("url")
        method = config.get("method", "POST")
        timeout_seconds = float(config.get("timeout_seconds", 10))
        max_attempts = int(config.get("max_attempts", 3))
        headers, secret_refs = await self._resolve_headers(
            headers_config=config.get("headers", {}) or {}
        )

        if not url:
            raise DomainValidationException(message="tool_config_missing_url")

        await self.repository.update_tool_run_result(
            tool_run_id=tool_run.tool_run_id,
            status=RunStatus.RUNNING,
            canonical_status=ToolRunStatus.EXECUTING,
            output={},
            error={},
        )

        request_body = tool_run.input or {}
        request_size = len(json.dumps(request_body, default=str).encode("utf-8"))
        attempt = 0
        started_at = time.monotonic()
        result: dict | None = None
        try:
            span_cm = (
                self.tracer.start_tool_span(
                    tool_id=str(tool_run.tool_config_id), input={"headers": list(headers.keys())}
                )
                if self.tracer
                else contextlib.nullcontext()
            )
            if secret_refs:
                flow_run_id = await self.repository.get_flow_run_id_for_tool_run(tool_run.tool_run_id)
                session_id, tenant_id = await self.repository.get_flow_context(flow_run_id)
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.SecretAccessed,
                    payload={
                        "tool_run_id": str(tool_run.tool_run_id),
                        "tool_config_id": str(tool_run.tool_config_id),
                        "secret_refs": secret_refs,
                    },
                    correlation_id=tool_run.correlation_id,
                    causation_id=None,
                    schema_version=1,
                )
            async with span_cm:
                async for retry_state in AsyncRetrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
                    reraise=True,
                ):
                    with retry_state:
                        attempt = retry_state.attempt_number
                        result = await self.executor.execute_http(
                            method=method,
                            url=url,
                            headers=headers,
                            json_body=request_body,
                            timeout_seconds=timeout_seconds,
                        )
                        try:
                            HttpToolResult.model_validate(result)
                        except ValidationError as validation_error:
                            raise DomainValidationException(
                                message="tool_response_validation_failed",
                                detail=validation_error.errors(),
                            ) from validation_error
        except Exception as exc:
            latency_ms = int((time.monotonic() - started_at) * 1000)
            retries = max(attempt - 1, 0)
            flow_run_id = await self.repository.get_flow_run_id_for_tool_run(tool_run.tool_run_id)
            session_id, tenant_id = await self.repository.get_flow_context(flow_run_id)
            if isinstance(exc, DomainValidationException):
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.ValidationFailed,
                    payload={
                        "tool_run_id": str(tool_run.tool_run_id),
                        "tool_config_id": str(tool_run.tool_config_id),
                        "error_class": type(exc).__name__,
                        "message": exc.message,
                    },
                    correlation_id=tool_run.correlation_id,
                    causation_id=None,
                    schema_version=1,
                )
            await self.repository.update_tool_run_result(
                tool_run_id=tool_run.tool_run_id,
                status=RunStatus.FAILED,
                canonical_status=ToolRunStatus.ERROR,
                output={},
                error={"error": str(exc)},
            )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.ToolInvocationFailed,
                payload={
                    "tool_run_id": str(tool_run.tool_run_id),
                    "tool_config_id": str(tool_run.tool_config_id),
                    "executor_type": "http",
                    "latency_ms": latency_ms,
                    "request_size": request_size,
                    "response_size": 0,
                    "retries": retries,
                    "error_class": type(exc).__name__,
                },
                correlation_id=tool_run.correlation_id,
                causation_id=None,
                schema_version=1,
            )
            await self.repository.create_run_failure_for_tool_run(
                tool_run_id=tool_run.tool_run_id,
                correlation_id=tool_run.correlation_id,
                error_type="tool_execution_error"
                if not isinstance(exc, DomainValidationException)
                else "tool_response_validation_failed",
                error={"error": str(exc)},
            )
            raise

        if result is None:
            raise DomainValidationException(message="tool_executor_empty_result")
        latency_ms = int((time.monotonic() - started_at) * 1000)
        retries = max(attempt - 1, 0)
        response_size = len(result.get("text", "").encode("utf-8")) if isinstance(result, dict) else 0
        flow_run_id = await self.repository.get_flow_run_id_for_tool_run(tool_run.tool_run_id)
        session_id, tenant_id = await self.repository.get_flow_context(flow_run_id)
        await self.repository.update_tool_run_result(
            tool_run_id=tool_run.tool_run_id,
            status=RunStatus.COMPLETED,
            canonical_status=ToolRunStatus.SUCCESS,
            output=result,
            error={},
        )
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.ToolInvocationSucceeded,
            payload={
                "tool_run_id": str(tool_run.tool_run_id),
                "tool_config_id": str(tool_run.tool_config_id),
                "executor_type": "http",
                "latency_ms": latency_ms,
                "request_size": request_size,
                "response_size": response_size,
                "retries": retries,
            },
            correlation_id=tool_run.correlation_id,
            causation_id=None,
            schema_version=1,
        )
        await self.repository.create_response_artifact_for_tool_run(
            tool_run_id=tool_run.tool_run_id,
            payload={"type": "tool_result", "tool_run_id": str(tool_run.tool_run_id), "result": result},
        )

        return result
