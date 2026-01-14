from __future__ import annotations

from typing import Protocol, Dict, Any
from uuid import UUID

from domain.execution.schemas.trace import TraceContext
from domain.llm.schemas.llm import LLMRequest, LLMResult


class LLMExecutorPort(Protocol):
    async def execute_llm(
        self,
        *,
        request: LLMRequest,
        trace: TraceContext,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None = None,
        provider: str = "OPENAI",
        policy_llm: Dict[str, Any] | None = None,
    ) -> LLMResult:  # pragma: no cover - interface
        ...
