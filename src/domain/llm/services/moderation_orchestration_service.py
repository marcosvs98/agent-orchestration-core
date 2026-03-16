from __future__ import annotations

from domain.llm.ports.moderation_provider import ModerationProviderPort
from domain.llm.schemas.moderation import ModerationResult


class ModerationProviderSelector:
    def __init__(
        self,
        *,
        slm_provider: ModerationProviderPort | None,
        openai_provider: ModerationProviderPort | None,
    ) -> None:
        self._providers_by_name: dict[str, ModerationProviderPort] = {}
        if slm_provider is not None:
            self._providers_by_name["SLM"] = slm_provider
            self._providers_by_name["SLM_LOCAL"] = slm_provider
        if openai_provider is not None:
            self._providers_by_name["OPENAI"] = openai_provider

    def select(
        self, config: dict[str, object]
    ) -> list[tuple[ModerationProviderPort, dict[str, object]]]:
        primary_cfg = self._resolve_provider_cfg(config, "primary")
        fallback_cfg = self._resolve_provider_cfg(config, "fallback")
        ordered: list[tuple[ModerationProviderPort, dict[str, object]]] = []
        for cfg in [primary_cfg, fallback_cfg]:
            provider_name = str(cfg.get("provider", "")).upper()
            provider = self._providers_by_name.get(provider_name)
            if provider is not None:
                ordered.append((provider, cfg))
        return ordered

    @staticmethod
    def _resolve_provider_cfg(
        config: dict[str, object], key: str
    ) -> dict[str, object]:
        provider_cfg = config.get(key)
        if isinstance(provider_cfg, dict):
            return dict(provider_cfg)
        if key == "primary":
            return {"provider": str(config.get("primary_provider", "SLM"))}
        return {}


class ModerationOrchestrationService(ModerationProviderPort):
    def __init__(
        self,
        *,
        slm_provider: ModerationProviderPort | None,
        openai_provider: ModerationProviderPort | None,
        default_config: dict[str, object] | None = None,
    ) -> None:
        self.slm_provider = slm_provider
        self.openai_provider = openai_provider
        self.default_config = default_config or {}
        self.provider_selector = ModerationProviderSelector(
            slm_provider=slm_provider,
            openai_provider=openai_provider,
        )

    async def moderate(
        self, text: str, config: dict[str, object] | None = None
    ) -> ModerationResult:
        merged_config = dict(self.default_config)
        if config:
            merged_config.update(config)
        ordered_providers = self.provider_selector.select(merged_config)
        fallback_enabled = bool(merged_config.get("fallback_enabled", True))
        failures = 0
        for provider, provider_cfg in ordered_providers:
            try:
                cfg = dict(provider_cfg)
                for key in (
                    "prompt_key",
                    "prompt_text",
                    "output_schema",
                    "temperature",
                    "max_tokens",
                ):
                    if key in merged_config:
                        cfg[key] = merged_config[key]
                return await provider.moderate(text=text, config=cfg)
            except Exception:
                failures += 1
                if failures >= 1 and not fallback_enabled:
                    break
                continue
        return ModerationResult(flagged=False, categories={})
