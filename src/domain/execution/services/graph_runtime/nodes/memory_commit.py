from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from domain.context.ports.service import MemoryWriteServicePort
from domain.context.schemas.memory_write import MemoryWriteEventContext
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.graph_runtime.types import (
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType
from exceptions.service_exceptions import BaseServiceException


class MemoryCommitMergeErrorCode(StrEnum):
    RULE_INVALID = "memory_commit_data_merge_rule_invalid"
    MISSING_FROM_NODE_ID = "memory_commit_data_merge_missing_from_node_id"
    MISSING_TARGET_KEY = "memory_commit_data_merge_missing_target_key"
    RESOLVED_DATA_EMPTY = "memory_commit_resolved_data_empty"


class MemoryCommitPayloadState(StrEnum):
    PENDING_PERSIST = "pending_persist"


class MemoryCommitSuccessReason(StrEnum):
    PAYLOAD_READY = "memory_commit_payload_ready"


def _get_value_at_path(obj: Any, path: str) -> Any:
    if path == "":
        return obj
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _resolve_memory_commit_data(
    *,
    cfg: dict[str, Any],
    context: ExecutionContext,
) -> tuple[dict[str, Any] | None, str | None]:
    merged: dict[str, Any] = {}
    base = cfg.get("data")
    if isinstance(base, dict):
        merged.update(base)
    snap = context.state.get(NODE_OUTPUTS_BY_NODE_ID_KEY)
    if not isinstance(snap, dict):
        snap = {}
    rules = cfg.get("data_merge")
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                return None, MemoryCommitMergeErrorCode.RULE_INVALID.value
            fid = rule.get("from_node_id")
            path_raw = rule.get("path", "")
            target = rule.get("target_key")
            if not fid or not isinstance(fid, str):
                return None, MemoryCommitMergeErrorCode.MISSING_FROM_NODE_ID.value
            if not target or not isinstance(target, str):
                return None, MemoryCommitMergeErrorCode.MISSING_TARGET_KEY.value
            path = path_raw if isinstance(path_raw, str) else ""
            node_out = snap.get(fid)
            if not isinstance(node_out, dict):
                continue
            val = _get_value_at_path(node_out, path)
            if val is None:
                continue
            merged[target] = val
    overlay = cfg.get("literal_overlay")
    overlay_applied = False
    if isinstance(overlay, dict):
        if overlay:
            overlay_applied = True
        merged.update(overlay)
    has_merge_rules = isinstance(rules, list) and len(rules) > 0
    if not merged:
        if has_merge_rules or overlay_applied:
            return None, MemoryCommitMergeErrorCode.RESOLVED_DATA_EMPTY.value
        merged = {}
    return merged, None


class MemoryCommitNode:
    node_type = NodeType.MemoryCommitNode
    side_effect = False
    deterministic = True

    def __init__(
        self,
        *,
        memory_write_service: MemoryWriteServicePort | None = None,
        execution_repository: ExecutionRepository | None = None,
        tracer: RuntimeTracerPort | None = None,
    ) -> None:
        self.memory_write_service = memory_write_service
        self.execution_repository = execution_repository
        self.tracer = tracer

    async def _persist_memory_item(
        self,
        *,
        context: ExecutionContext,
        memory_item: dict[str, Any],
    ) -> None:
        if self.memory_write_service is None or self.execution_repository is None:
            return
        try:
            node_uuid = UUID(str(context.current_node_id))
        except ValueError:
            return
        node = await self.execution_repository.get_node(node_uuid)
        if node is None or not bool(node.allow_memory_write):
            return
        try:
            await self.memory_write_service.write_memory_item(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                item=memory_item,
                event_context=MemoryWriteEventContext(
                    session_id=context.session_id,
                    flow_run_id=context.flow_run_id,
                    correlation_id=context.correlation_id,
                    causation_id=context.current_node_run_id,
                    node_id=node_uuid,
                ),
            )
        except BaseServiceException as exc:
            return

    async def execute(
        self, context: ExecutionContext, config: dict[str, Any] | None = None
    ) -> NodeResult:
        cfg = config or {}
        schema_id = cfg.get("schema_id")
        rag_raw = cfg.get("rag_config_id")
        if not schema_id or not rag_raw:
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.ERROR,
                data={
                    "error": "memory_commit_invalid_config",
                    "reason_code": "memory_commit_invalid_config",
                },
            )
        try:
            UUID(str(rag_raw))
        except ValueError:
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.ERROR,
                data={
                    "error": "memory_commit_invalid_rag_config_id",
                    "reason_code": "memory_commit_invalid_rag_config_id",
                },
            )
        source_raw = cfg.get("source", "explicit_user")
        data, reason = _resolve_memory_commit_data(cfg=cfg, context=context)
        if data is None:
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.ERROR,
                data={
                    "error": reason or "memory_commit_merge_failed",
                    "reason_code": reason,
                },
            )

        memory_item = {
            "schema_id": str(schema_id),
            "schema_version": int(cfg.get("schema_version") or 1),
            "data": data,
            "source": str(source_raw),
            "rag_config_id": str(rag_raw),
        }
        await self._persist_memory_item(
            context=context,
            memory_item=memory_item,
        )
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data={
                "memory_commit": MemoryCommitPayloadState.PENDING_PERSIST.value,
                "reason_code": MemoryCommitSuccessReason.PAYLOAD_READY.value,
            },
            memory=[*context.memory, memory_item],
        )
