from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.schemas.tool_executor import (
    ToolExecutionMode,
    ToolExecutorOutput,
    ToolRunInput,
    ToolRunResult,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
    OperationStatus,
)
from domain.prompts.schemas.prompt import NodeType
from exceptions.service_exceptions import DomainValidationException
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.tools.services.tool_orchestrator import ToolOrchestrator


class _ParamExtractionOperation(BaseModel):
    operation_id: str
    tool_name: str
    status: OperationStatus
    params: dict[str, Any] = Field(default_factory=dict)


class _SelectedTool(BaseModel):
    name: str
    tool_config_id: str


class _ToolSelectionItem(BaseModel):
    selected_tool: _SelectedTool


class ToolExecutor(NodeExecutor):
    node_type = NodeType.ToolExecutor
    side_effect = True
    deterministic = False

    def __init__(
        self,
        tool_orchestrator: ToolOrchestrator,
        execution_repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self.tracer = tracer

    async def execute(
        self,
        context: ExecutionContext,
        config: dict[str, Any] | None = None,
    ) -> NodeResult:
        try:
            inputs, precomputed_results = await self._parse_inputs_from_context(context)
        except DomainValidationException as exc:
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.ERROR,
                error={"message": exc.message, "detail": exc.detail},
                next_state=context.state,
            )

        runtime_policy = (context.metadata or {}).get("runtime_policy") or {}
        if not isinstance(runtime_policy, dict):
            runtime_policy = {}
        limits_raw = runtime_policy.get("limits")
        limits = limits_raw if isinstance(limits_raw, dict) else {}
        raw_fanout = limits.get("tool_fanout_max_concurrency", 4)
        if raw_fanout is None:
            raw_fanout = 4
        max_concurrency = max(1, int(raw_fanout))

        semaphore = asyncio.Semaphore(max_concurrency)

        tasks = [
            self._execute_one(semaphore=semaphore, context=context, tool_run=tool_run)
            for tool_run in inputs
        ]

        gathered_results = await asyncio.gather(*tasks) if tasks else []
        results = [*precomputed_results, *gathered_results]

        execution_output = ToolExecutorOutput(result=list(results))
        data = execution_output.model_dump(mode="json")

        next_state = {**(context.state or {}), self.node_type.value: data}

        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=data,
            next_state=next_state,
        )

    async def _execute_one(
        self,
        semaphore: asyncio.Semaphore,
        context: ExecutionContext,
        tool_run: ToolRunInput,
    ) -> ToolRunResult:
        idempotency_key = f"{context.flow_run_id}:{context.current_node_run_id}:{tool_run.operation_id}"
        async with semaphore:
            tool_run_id: UUID | None = None
            try:
                tool_run_id = await self.execution_repository.create_tool_run(
                    tool_config_id=UUID(tool_run.tool_config_id),
                    correlation_id=context.correlation_id,
                    agent_run_id=None,
                    node_run_id=context.current_node_run_id,
                    idempotency_key=idempotency_key,
                    has_side_effect=True,
                    input_payload=tool_run.params,
                )
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.execution.nodes.tool_execution.execute_tool_run",
                    input={
                        "tool_run_id": str(tool_run_id),
                        "operation_id": tool_run.operation_id,
                    },
                ) as tool_span:
                    try:
                        result = await self.tool_orchestrator.execute_tool_run(
                            tool_run_id=tool_run_id
                        )
                        tool_run_result = ToolRunResult(
                            operation_id=tool_run.operation_id,
                            tool_name=tool_run.tool_name,
                            execution_mode=ToolExecutionMode.IMMEDIATE,
                            status=OperationStatus.SUCCESS,
                            result=result,
                        )
                        tool_span.update(output=tool_run_result.model_dump(mode="json"))
                        return tool_run_result
                    except Exception as exc:
                        tool_run_result = ToolRunResult(
                            operation_id=tool_run.operation_id,
                            tool_name=tool_run.tool_name,
                            execution_mode=ToolExecutionMode.IMMEDIATE,
                            status=OperationStatus.ERROR,
                            result=self._error_payload(
                                exc=exc,
                                fallback_message="tool_execution_failed",
                                tool_run_id=tool_run_id,
                            ),
                        )
                        tool_span.update(output=tool_run_result.model_dump(mode="json"))
                        return tool_run_result
            except Exception as exc:
                return ToolRunResult(
                    operation_id=tool_run.operation_id,
                    tool_name=tool_run.tool_name,
                    execution_mode=ToolExecutionMode.IMMEDIATE,
                    status=OperationStatus.ERROR,
                    result=self._error_payload(
                        exc=exc,
                        fallback_message="tool_run_creation_failed",
                        tool_run_id=tool_run_id,
                    ),
                )

    @staticmethod
    def _error_payload(
        *,
        exc: Exception,
        fallback_message: str,
        tool_run_id: UUID | None = None,
    ) -> dict[str, Any]:
        if isinstance(exc, DomainValidationException):
            payload: dict[str, Any] = {
                "message": exc.message,
                "detail": exc.detail,
            }
        else:
            payload = {
                "message": fallback_message,
                "error_class": type(exc).__name__,
            }
        if tool_run_id is not None:
            payload["tool_run_id"] = str(tool_run_id)
        return payload

    async def _parse_inputs_from_context(
        self, context: ExecutionContext
    ) -> tuple[list[ToolRunInput], list[ToolRunResult]]:
        param_out = context.get_node_output(NodeType.ToolInputFiller)
        raw_result = param_out.get("result")
        strict_mode = await self._strict_contract_mode(context)

        if raw_result is None:
            if strict_mode:
                raise DomainValidationException(
                    message="param_extraction_result_missing"
                )
            return [], []

        parsed_operations: list[_ParamExtractionOperation] = []

        for item in raw_result:
            try:
                parsed_operations.append(_ParamExtractionOperation.model_validate(item))
            except ValidationError as exc:
                if strict_mode:
                    raise DomainValidationException(
                        message="param_extraction_operation_invalid",
                        detail=exc.errors(),
                    ) from exc

        ready_operations = [
            operation
            for operation in parsed_operations
            if operation.status == OperationStatus.READY
        ]

        if not ready_operations:
            return [], []
        tool_slice = context.get_node_output(NodeType.ToolResolver)

        configs_by_name = await self._build_tool_config_map(tool_slice, strict_mode)

        inputs: list[ToolRunInput] = []
        precomputed_results: list[ToolRunResult] = []

        for operation in ready_operations:
            configs = configs_by_name.get(operation.tool_name, set())
            if not configs:
                if strict_mode:
                    raise DomainValidationException(
                        message="ready_operation_tool_config_unresolved",
                        detail={
                            "tool_name": operation.tool_name,
                            "operation_id": operation.operation_id,
                        },
                    )
                precomputed_results.append(
                    ToolRunResult(
                        operation_id=operation.operation_id,
                        tool_name=operation.tool_name,
                        execution_mode=ToolExecutionMode.IMMEDIATE,
                        status=OperationStatus.ERROR,
                        result={
                            "message": "ready_operation_tool_config_unresolved",
                            "tool_name": operation.tool_name,
                        },
                    )
                )
                continue
            if len(configs) > 1:
                if strict_mode:
                    raise DomainValidationException(
                        message="ready_operation_tool_config_ambiguous",
                        detail={
                            "tool_name": operation.tool_name,
                            "tool_config_ids": sorted(configs),
                            "operation_id": operation.operation_id,
                        },
                    )
                precomputed_results.append(
                    ToolRunResult(
                        operation_id=operation.operation_id,
                        tool_name=operation.tool_name,
                        execution_mode=ToolExecutionMode.IMMEDIATE,
                        status=OperationStatus.ERROR,
                        result={
                            "message": "ready_operation_tool_config_ambiguous",
                            "tool_name": operation.tool_name,
                            "tool_config_ids": sorted(configs),
                        },
                    )
                )
                continue
            tool_config_id = next(iter(configs))
            inputs.append(
                ToolRunInput(
                    operation_id=operation.operation_id,
                    tool_name=operation.tool_name,
                    tool_config_id=tool_config_id,
                    params=operation.params,
                )
            )

        return inputs, precomputed_results

    @staticmethod
    async def _build_tool_config_map(
        tool_slice: dict[str, Any],
        strict_mode: bool,
    ) -> dict[str, set[str]]:
        raw_result = tool_slice.get("result")

        if not isinstance(raw_result, list):
            if strict_mode:
                raise DomainValidationException(message="tool_selection_result_invalid")
            raw_result = []

        configs_by_name: dict[str, set[str]] = {}

        for item in raw_result:
            try:
                parsed_item = _ToolSelectionItem.model_validate(item)
            except ValidationError as exc:
                if strict_mode:
                    raise DomainValidationException(
                        message="tool_selection_item_invalid",
                        detail=exc.errors(),
                    ) from exc
                continue

            tool_name = parsed_item.selected_tool.name
            tool_config_id = parsed_item.selected_tool.tool_config_id

            if tool_name not in configs_by_name:
                configs_by_name[tool_name] = set()

            configs_by_name[tool_name].add(tool_config_id)

        return configs_by_name

    @staticmethod
    async def _strict_contract_mode(context: ExecutionContext) -> bool:
        metadata = context.metadata if isinstance(context.metadata, dict) else {}
        runtime_policy = metadata.get("runtime_policy")

        if not isinstance(runtime_policy, dict):
            return False

        execution_policy = runtime_policy.get("execution")

        if not isinstance(execution_policy, dict):
            return False

        return bool(execution_policy.get("strict_contract_mode", False))
