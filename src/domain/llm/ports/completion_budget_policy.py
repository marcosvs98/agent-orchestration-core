from __future__ import annotations

from typing import Any, Protocol


class CompletionBudgetPolicyPort(Protocol):
    def compute_max_tokens(
        self,
        provider_model: str,
        user_message: str,
        output_schema: dict[str, Any],
        policy_max: int | None = None,
        completion_budget: dict[str, Any] | None = None,
    ) -> int: ...
