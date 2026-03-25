from __future__ import annotations

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.schemas.context_layers import LayerUsageDecision
from domain.llm.schemas.llm import LLMTaskType


class RuntimeContextLayerPolicy:
    def decide(
        self,
        *,
        task_type: LLMTaskType,
        task_flags: AITaskContextFlags | None = None,
    ) -> LayerUsageDecision:
        if task_flags is not None:
            return LayerUsageDecision.from_ai_task_flags(
                allow_rag_tenant=task_flags.allow_rag_tenant,
                allow_user_memory_structured=task_flags.allow_user_memory_structured,
                allow_user_memory_vector=task_flags.allow_user_memory_vector,
                allow_session_context=task_flags.allow_session_context,
                allow_memory_write=task_flags.allow_memory_write,
            )
        return LayerUsageDecision()
