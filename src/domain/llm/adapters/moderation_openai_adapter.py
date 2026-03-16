from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from openai import AsyncOpenAI
from openai.types.moderation import Moderation
from openai.types.moderation_create_response import ModerationCreateResponse

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.llm.schemas.moderation import ModerationResult


DEFAULT_TIMEOUT = 1
DEFAULT_CACHE_TTL = 86400
DEFAULT_CATEGORY_THRESHOLDS: dict[str, float] = {
    "illicit": 0.85,
    "hate": 0.5,
    "harassment": 0.5,
    "self_harm": 0.5,
    "sexual": 0.5,
    "violence": 0.5,
}


class ModerationOpenAIAdapter:
    def __init__(
        self,
        client: AsyncOpenAI,
        cache_adapter: RedisAdapter,
        tracer: RuntimeTracerPort,
        model: str,
        timeout: int = DEFAULT_TIMEOUT,
        category_thresholds: dict[str, float] | None = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ) -> None:
        self.client = client
        self.cache_adapter = cache_adapter
        self.tracer = tracer
        self.model = model
        self.timeout = timeout
        self.category_thresholds = category_thresholds or DEFAULT_CATEGORY_THRESHOLDS
        self.cache_ttl = cache_ttl

    async def moderate(
        self, text: str, config: dict[str, object] | None = None
    ) -> ModerationResult:
        cfg = config or {}
        model = str(
            cfg.get("model_alias")
            or cfg.get("openai_model_alias")
            or cfg.get("openai_model")
            or self.model
        )
        timeout = self._resolve_timeout_seconds(cfg)
        threshold_config = cfg.get("category_thresholds")
        thresholds = self._resolve_thresholds(threshold_config)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = f"moderation:{model}:{text_hash}"
        cached = await self.cache_adapter.get(cache_key)
        if cached is not None:
            return ModerationResult.model_validate(cached)
        with self.tracer.observe(
            as_type="guardrail",
            name="domain.llm.adapters.moderation_openai_adapter.moderate",
            input={"text_hash": text_hash[:16], "model": model},
        ) as guardrail_handle:
            try:
                moderation: ModerationCreateResponse = (
                    await self.client.moderations.create(
                        input=text,
                        timeout=timeout,
                        model=model,
                    )
                )
                result: Moderation = moderation.results[0]
                categories_raw = result.categories.model_dump()
                scores_raw = result.category_scores.model_dump()
                all_keys = set(categories_raw.keys()) | set(scores_raw.keys())
                categories: dict[str, dict[str, Any]] = {}
                custom_flagged = False
                for key in all_keys:
                    score = float(scores_raw.get(key, 0.0))
                    api_flagged = bool(categories_raw.get(key, False))
                    threshold = thresholds.get(key, 0.5)
                    actually_flagged = score >= threshold
                    categories[key] = {
                        "flagged": actually_flagged,
                        "score": score,
                        "api_flagged": api_flagged,
                        "threshold": threshold,
                    }
                    if actually_flagged:
                        custom_flagged = True
                moderation_result = ModerationResult(
                    flagged=custom_flagged,
                    categories=categories,
                )
                await self.cache_adapter.set(
                    cache_key,
                    moderation_result.model_dump(mode="json"),
                    ttl=self.cache_ttl,
                )
                guardrail_handle.success(
                    output={
                        "flagged": moderation_result.flagged,
                        "action": "block" if moderation_result.flagged else "allow",
                    }
                )
                return moderation_result
            except Exception:
                guardrail_handle.error(
                    error_type="ModerationAPIError",
                    error_message="OpenAI moderation API failed",
                )
                return ModerationResult(flagged=False, categories={})

    def _resolve_timeout_seconds(self, cfg: dict[str, object]) -> float:
        timeout_ms = cfg.get("timeout_ms")
        if timeout_ms is not None:
            try:
                return max(float(timeout_ms) / 1000.0, 0.001)
            except (TypeError, ValueError):
                pass
        timeout_s = cfg.get("timeout_s")
        if timeout_s is not None:
            try:
                return float(timeout_s)
            except (TypeError, ValueError):
                pass
        openai_timeout_s = cfg.get("openai_timeout_s")
        if openai_timeout_s is not None:
            try:
                return float(openai_timeout_s)
            except (TypeError, ValueError):
                pass
        return float(self.timeout)

    def _resolve_thresholds(self, raw: object) -> dict[str, float]:
        if not isinstance(raw, Mapping):
            return self.category_thresholds
        resolved: dict[str, float] = dict(self.category_thresholds)
        for key, value in raw.items():
            try:
                resolved[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return resolved
