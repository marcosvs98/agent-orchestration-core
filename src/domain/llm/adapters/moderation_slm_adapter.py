from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from domain.llm.adapters.slm_local_provider import SLMLocalProvider
from domain.llm.schemas.llm import LLMRequest
from domain.llm.schemas.moderation import ModerationResult

if TYPE_CHECKING:
    from domain.prompts.services.prompt_service import PromptService


class ModerationSLMAdapter:
    def __init__(
        self,
        slm_provider: SLMLocalProvider | None,
        prompt_text: str | None,
        output_schema: dict[str, object] | None,
        prompt_service: PromptService | None,
        prompt_key: str,
        model_alias: str,
        slm_timeout_s: float,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.slm_provider = slm_provider
        self._prompt_text = prompt_text
        self._output_schema = output_schema
        self.prompt_service = prompt_service
        self.prompt_key = prompt_key
        self.model_alias = model_alias
        self.slm_timeout_s = slm_timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._load_lock = asyncio.Lock()

    async def _ensure_prompt_loaded(self, prompt_key: str) -> tuple[str, dict[str, object]]:
        if self._prompt_text is not None and self._output_schema is not None:
            return self._prompt_text, self._output_schema
        if self.prompt_service is None:
            raise RuntimeError("prompt_service_unavailable")
        async with self._load_lock:
            if self._prompt_text is None or self._output_schema is None:
                prompt = await self.prompt_service.get_prompt(prompt_key)
                if prompt is None:
                    raise RuntimeError("prompt_not_found")
                output_schema = prompt.output_schema
                if not isinstance(output_schema, dict):
                    raise RuntimeError("prompt_output_schema_missing")
                self._prompt_text = prompt.template_text
                self._output_schema = output_schema
        return self._prompt_text, self._output_schema

    async def moderate(
        self, text: str, config: dict[str, object] | None = None
    ) -> ModerationResult:
        if self.slm_provider is None:
            raise RuntimeError("slm_provider_unavailable")
        cfg = config or {}
        prompt_text = cfg.get("prompt_text")
        output_schema = cfg.get("output_schema")
        prompt_key = str(cfg.get("prompt_key") or self.prompt_key)
        model_alias = str(cfg.get("model_alias") or cfg.get("slm_model_alias") or self.model_alias)
        max_tokens = int(cfg.get("max_tokens") or self.max_tokens)
        resolved_prompt_text, resolved_output_schema = await self._resolve_prompt(
            prompt_text=prompt_text,
            output_schema=output_schema,
            prompt_key=prompt_key,
        )
        request = LLMRequest(
            prompt=resolved_prompt_text.strip(),
            user_message=text,
            model_alias=model_alias,
            json_schema=resolved_output_schema,
            temperature=cfg.get("temperature"),
            max_latency_ms=cfg.get("timeout_ms"),
            max_tokens=max_tokens,
        )
        llm_result = await self.slm_provider.infer(request)
        output = llm_result.output if isinstance(llm_result.output, dict) else {}
        result_obj = output.get("result")
        result_data = result_obj if isinstance(result_obj, dict) else output
        flagged = bool(result_data.get("flagged", False))
        raw_categories = result_data.get("categories")
        categories = self._normalize_categories(raw_categories)
        return ModerationResult(flagged=flagged, categories=categories)

    async def _resolve_prompt(
        self,
        *,
        prompt_text: object,
        output_schema: object,
        prompt_key: str,
    ) -> tuple[str, dict[str, object]]:
        if isinstance(prompt_text, str) and isinstance(output_schema, dict):
            return prompt_text, output_schema
        return await self._ensure_prompt_loaded(prompt_key=prompt_key)

    @staticmethod
    def _normalize_categories(
        raw_categories: object,
    ) -> dict[str, dict[str, bool | float]]:
        if not isinstance(raw_categories, Mapping):
            return {}
        categories: dict[str, dict[str, bool | float]] = {}
        for key, value in raw_categories.items():
            normalized_key = str(key)
            if not isinstance(value, Mapping):
                categories[normalized_key] = {"flagged": False, "score": 0.0}
                continue
            categories[normalized_key] = {
                "flagged": bool(value.get("flagged", False)),
                "score": float(value.get("score", 0.0)),
            }
        return categories
