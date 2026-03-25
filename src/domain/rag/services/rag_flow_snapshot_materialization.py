from __future__ import annotations

from uuid import UUID

from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.utils.rag_snapshot_hash import rag_materialization_sha256


async def resolve_frozen_rag_snapshot_fields(
    *,
    tenant_id: UUID,
    rag_config_id: UUID | None,
    rag_repository: RagRepository,
    rag_policy_service: RagPolicyService,
) -> tuple[UUID | None, UUID | None, UUID | None, str | None]:
    if rag_config_id is None:
        return None, None, None, None
    config = await rag_repository.get_rag_config(rag_config_id)
    if config is None or config.tenant_id != tenant_id:
        return None, None, None, None
    rule = await rag_repository.get_chunking_rule(
        tenant_id=tenant_id,
        rag_chunking_rule_id=config.chunking_rule_id,
    )
    if rule is None:
        return rag_config_id, None, None, None
    resolved = await rag_policy_service.resolve(tenant_id=tenant_id)
    policy_definition: dict = {}
    policy_vid: UUID | None = None
    if resolved.policy_version_id is not None and resolved.definition is not None:
        policy_vid = resolved.policy_version_id
        policy_definition = resolved.definition.model_dump(mode="json")
    params_raw = rule.params if type(rule.params) is dict else {}
    materialization_hash = rag_materialization_sha256(
        rag_config_id=rag_config_id,
        chunking_rule_id=rule.rag_chunking_rule_id,
        params=params_raw,
        policy_definition=policy_definition,
    )
    return (
        rag_config_id,
        rule.rag_chunking_rule_id,
        policy_vid,
        materialization_hash,
    )
