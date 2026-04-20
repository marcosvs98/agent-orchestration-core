"""RuntimeContextLayerPolicy.decide branches."""

from __future__ import annotations

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.services.runtime_policy import RuntimeContextLayerPolicy
from domain.llm.schemas.llm import LLMTaskType


def test_decide_with_ai_task_flags() -> None:
    flags = AITaskContextFlags(
        allow_rag_tenant=True,
        allow_user_memory_structured=True,
        allow_user_memory_vector=False,
        allow_session_context=True,
        allow_memory_write=True,
    )
    out = RuntimeContextLayerPolicy.decide(
        task_type=LLMTaskType.RESPONSE_RENDER,
        task_flags=flags,
    )
    assert out is not None


def test_decide_without_flags_returns_default_decision() -> None:
    out = RuntimeContextLayerPolicy.decide(
        task_type=LLMTaskType.RESPONSE_RENDER,
        task_flags=None,
    )
    assert out is not None
