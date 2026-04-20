from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.context.schemas.memory_write import MemoryWriteEventContext, MemoryWriteResult
from domain.context.services.memory_extraction_processor import MemoryExtractionProcessor
from domain.governance.schemas.memory_policy import (
    MemoryPolicyDefinition,
    MemoryPolicySource,
    ResolvedMemoryPolicy,
    ResolvedMemoryPolicySource,
)
from domain.llm.schemas.llm import LLMResult


class _Obs:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def success(self, **kwargs):
        return None

    def failure(self, **kwargs):
        return None


@pytest.fixture
def tracer() -> MagicMock:
    t = MagicMock()
    t.observe = MagicMock(return_value=_Obs())
    return t


def _base_config(*, enabled: bool = True) -> dict[str, object]:
    return {
        "enabled": enabled,
        "rag_config_id": str(uuid.uuid4()),
        "preference_schema_id": "user.preference.v1",
        "profile_schema_id": "user.profile_signal.v1",
        "llm": {
            "provider": "OPENAI",
            "model_alias": "gpt-4o-mini",
            "prompt": "Extract",
        },
    }


def _resolved_policy(*, allow_inferred: bool) -> ResolvedMemoryPolicy:
    sources = [MemoryPolicySource.EXPLICIT_USER]
    if allow_inferred:
        sources.append(MemoryPolicySource.INFERRED_LLM)
    return ResolvedMemoryPolicy(
        source=ResolvedMemoryPolicySource.TENANT_ACTIVE,
        tenant_id=uuid.uuid4(),
        definition=MemoryPolicyDefinition(allowed_sources=sources),
    )


def _last_skip_reason(tracer: MagicMock) -> str:
    skipped = [
        c
        for c in tracer.observe.call_args_list
        if c.kwargs.get("name") == "domain.context.memory_extraction.skipped"
    ]
    return str(skipped[-1].kwargs["input"]["reason_code"])


def _policy_service_mock(*, allow_inferred: bool) -> MagicMock:
    svc = MagicMock()
    svc.resolve = AsyncMock(return_value=_resolved_policy(allow_inferred=allow_inferred))
    return svc


@pytest.mark.asyncio
async def test_memory_extraction_skipped_invalid_config(tracer: MagicMock) -> None:
    mpol = MagicMock()
    proc = MemoryExtractionProcessor(None, None, tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={},
        config_payload={},
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    mpol.resolve.assert_not_called()
    assert _last_skip_reason(tracer) == "invalid_config"


@pytest.mark.asyncio
async def test_memory_extraction_skipped_disabled(tracer: MagicMock) -> None:
    mpol = MagicMock()
    proc = MemoryExtractionProcessor(None, None, tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={},
        config_payload=_base_config(enabled=False),
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    mpol.resolve.assert_not_called()
    assert _last_skip_reason(tracer) == "disabled"


@pytest.mark.asyncio
async def test_memory_extraction_skipped_missing_llm(tracer: MagicMock) -> None:
    mpol = MagicMock()
    proc = MemoryExtractionProcessor(None, AsyncMock(), tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={"k": "v"},
        config_payload=_base_config(),
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    mpol.resolve.assert_not_called()
    assert _last_skip_reason(tracer) == "missing_llm_executor"


@pytest.mark.asyncio
async def test_memory_extraction_skipped_missing_memory_write(
    tracer: MagicMock,
) -> None:
    mpol = MagicMock()
    llm = AsyncMock()
    proc = MemoryExtractionProcessor(llm, None, tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={"k": "v"},
        config_payload=_base_config(),
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    mpol.resolve.assert_not_called()
    assert _last_skip_reason(tracer) == "missing_memory_write_service"


@pytest.mark.asyncio
async def test_memory_extraction_skipped_inferred_llm_not_allowed(
    tracer: MagicMock,
) -> None:
    mpol = _policy_service_mock(allow_inferred=False)
    llm = AsyncMock()
    mws = AsyncMock()
    proc = MemoryExtractionProcessor(llm, mws, tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={"k": "v"},
        config_payload=_base_config(),
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    llm.execute_llm.assert_not_called()
    assert _last_skip_reason(tracer) == "inferred_llm_not_allowed"


@pytest.mark.asyncio
async def test_memory_extraction_runs_llm_when_allowed(tracer: MagicMock) -> None:
    mpol = _policy_service_mock(allow_inferred=True)
    llm = AsyncMock(
        return_value=LLMResult(
            output={
                "preferences": [],
                "profile_patch": None,
                "vector_memory": [],
            }
        )
    )
    mws = AsyncMock(return_value=MemoryWriteResult(targets_applied=[]))
    proc = MemoryExtractionProcessor(llm, mws, tracer, mpol)
    await proc.execute(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        flow_output={"k": "v"},
        config_payload=_base_config(),
        event_context=MemoryWriteEventContext(),
        trace_id=uuid.uuid4(),
    )
    llm.execute_llm.assert_called_once()
    mws.write_memory_item.assert_not_called()
