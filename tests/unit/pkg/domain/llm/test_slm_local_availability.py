from pathlib import Path
from unittest.mock import MagicMock

import pytest

from domain.llm.adapters.moderation_slm_adapter import (
    ModerationSLMAdapter,
    build_moderation_slm_adapter,
)
from domain.llm.services.moderation_orchestration_service import ModerationProviderSelector
from domain.llm.utils.model_path import find_slm_model_path, resolve_slm_model_path
from exceptions.service_exceptions import DomainValidationException

MODERATION_CONFIG: dict[str, object] = {
    "primary": {"provider": "SLM_LOCAL"},
    "fallback": {"provider": "OPENAI"},
}


def _adapter_kwargs(slm_provider: object) -> dict[str, object]:
    return {
        "slm_provider": slm_provider,
        "prompt_text": None,
        "output_schema": None,
        "prompt_service": None,
        "prompt_key": "ContentModeration",
        "model_alias": "slm-local-moderation",
        "slm_timeout_s": 0.3,
        "temperature": 0.0,
        "max_tokens": 18,
    }


def test_find_returns_none_when_no_model_is_present(tmp_path: Path) -> None:
    assert find_slm_model_path(str(tmp_path / "absent")) is None


def test_find_returns_none_for_empty_path() -> None:
    assert find_slm_model_path("   ") is None


def test_find_locates_a_gguf_inside_a_directory(tmp_path: Path) -> None:
    model = tmp_path / "nested" / "model.gguf"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"")
    assert find_slm_model_path(str(tmp_path)) == str(model.resolve())


def test_resolve_raises_when_the_path_is_empty() -> None:
    with pytest.raises(DomainValidationException) as excinfo:
        resolve_slm_model_path("")
    assert excinfo.value.message == "llm_provider_missing_model_path"


def test_resolve_raises_when_no_model_is_found(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationException) as excinfo:
        resolve_slm_model_path(str(tmp_path / "absent"))
    assert excinfo.value.message == "llm_provider_invalid_model_path"


def test_moderation_adapter_is_not_built_without_a_provider() -> None:
    assert build_moderation_slm_adapter(**_adapter_kwargs(None)) is None


def test_moderation_adapter_is_built_when_a_provider_exists() -> None:
    adapter = build_moderation_slm_adapter(**_adapter_kwargs(MagicMock()))
    assert isinstance(adapter, ModerationSLMAdapter)


def test_selector_offers_only_openai_when_the_local_model_is_absent() -> None:
    openai_provider = MagicMock()
    selector = ModerationProviderSelector(slm_provider=None, openai_provider=openai_provider)

    ordered = selector.select(MODERATION_CONFIG)

    assert [provider for provider, _ in ordered] == [openai_provider]


def test_selector_offers_the_local_model_first_when_present() -> None:
    slm_provider = MagicMock()
    openai_provider = MagicMock()
    selector = ModerationProviderSelector(
        slm_provider=slm_provider, openai_provider=openai_provider
    )

    ordered = selector.select(MODERATION_CONFIG)

    assert [provider for provider, _ in ordered] == [slm_provider, openai_provider]


def test_provider_builder_returns_none_and_probes_only_once(monkeypatch) -> None:
    from domain.llm.adapters import slm_local_provider as module

    module.build_slm_local_provider.cache_clear()
    probes = {"n": 0}

    def _probe(_path: str) -> str | None:
        probes["n"] += 1
        return None

    monkeypatch.setattr(module, "find_slm_model_path", _probe)
    try:
        assert module.build_slm_local_provider() is None
        assert module.build_slm_local_provider() is None
        assert module.build_slm_local_provider() is None
        assert probes["n"] == 1
    finally:
        module.build_slm_local_provider.cache_clear()


def test_provider_builder_constructs_when_a_model_is_found(monkeypatch) -> None:
    from domain.llm.adapters import slm_local_provider as module

    module.build_slm_local_provider.cache_clear()
    sentinel = object()
    monkeypatch.setattr(module, "find_slm_model_path", lambda _path: "/models/m.gguf")
    monkeypatch.setattr(module, "SLMLocalProvider", lambda **_kwargs: sentinel)
    try:
        assert module.build_slm_local_provider() is sentinel
    finally:
        module.build_slm_local_provider.cache_clear()
