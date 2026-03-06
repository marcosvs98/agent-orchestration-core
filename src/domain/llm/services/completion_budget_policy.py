from __future__ import annotations

import orjson
from typing import Any

import tiktoken

from domain.execution.ports.runtime_tracer import RuntimeTracerPort


class CompletionBudgetPolicy:
    SCHEMA_FACTOR = 1.2
    SAFETY_MARGIN = 16
    FLOOR = 32

    def __init__(self, tracer: RuntimeTracerPort) -> None:
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self.tracer = tracer

    def compute_max_tokens(
        self,
        provider_model: str,
        user_message: str,
        output_schema: dict[str, Any],
        policy_max: int | None = None,
        completion_budget: dict[str, Any] | None = None,
    ) -> int:
        span_input = {
            "provider_model": provider_model,
            "policy_max": policy_max,
            "completion_budget": completion_budget,
        }
        with self.tracer.observe(
            as_type="span",
            name="domain.llm.completion_budget.compute_max_tokens",
            input=span_input,
        ) as span_handle:
            cb = completion_budget or {}
            schema_factor = cb.get("schema_factor", self.SCHEMA_FACTOR)
            safety_margin = cb.get("safety_margin", self.SAFETY_MARGIN)
            floor = cb.get("floor", self.FLOOR)
            schema_str = (
                orjson.dumps(output_schema).decode()
                if output_schema
                else "{}"
            )
            schema_tokens = len(self._encoding.encode(schema_str))
            raw = int(schema_tokens * schema_factor + safety_margin)
            out = max(floor, raw)
            if policy_max is not None and policy_max > 0:
                out = min(out, policy_max)
            if span_handle:
                span_handle.success(
                    output={
                        "max_tokens": out,
                        "schema_tokens": schema_tokens,
                        "raw_before_cap": raw,
                    }
                )
            return out
