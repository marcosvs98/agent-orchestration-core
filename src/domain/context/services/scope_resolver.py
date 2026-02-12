from __future__ import annotations

from domain.context.schemas.context_layers import ContextLayerScope

ALLOWED_FILTER_OVERRIDE_KEYS = {"tags", "namespace", "doc_type", "expires_after"}


def resolve_rag_scope(
    scope: ContextLayerScope,
    user_id: str | None = None,
    filters_override: dict[str, object] | None = None,
) -> tuple[dict[str, object], str | None]:
    base: dict[str, object]
    search_user_id: str | None
    if scope == ContextLayerScope.TENANT_KNOWLEDGE:
        base = {"scope": ContextLayerScope.TENANT_KNOWLEDGE.value}
        search_user_id = None
    else:
        base = {
            "scope": ContextLayerScope.USER_MEMORY.value,
            "user_id": user_id,
        }
        search_user_id = user_id
    if isinstance(filters_override, dict):
        merged = {
            k: v
            for k, v in filters_override.items()
            if k in ALLOWED_FILTER_OVERRIDE_KEYS
        }
        base.update(merged)
    return base, search_user_id
