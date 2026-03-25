from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any
from uuid import UUID


def normalize_json_for_rag_hash(value: Any) -> Any:
    if value is None:
        return None
    if type(value) is dict:
        return {
            k: normalize_json_for_rag_hash(value[k])
            for k in sorted(value.keys(), key=lambda x: str(x))
        }
    if type(value) is list:
        return [normalize_json_for_rag_hash(v) for v in value]
    if type(value) is UUID:
        return str(value).lower()
    if type(value) is bool or type(value) is int:
        return value
    if type(value) is float:
        return float(Decimal(str(value)))
    if type(value) is str:
        return value
    return value


def rag_materialization_canonical_string(
    *,
    rag_config_id: UUID,
    chunking_rule_id: UUID,
    params: dict[str, Any],
    policy_definition: dict[str, Any],
) -> str:
    body = {
        "rag_config_id": rag_config_id,
        "chunking_rule_id": chunking_rule_id,
        "params": params,
        "policy_definition": policy_definition,
    }
    normalized = normalize_json_for_rag_hash(body)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def rag_materialization_sha256(
    *,
    rag_config_id: UUID,
    chunking_rule_id: UUID,
    params: dict[str, Any],
    policy_definition: dict[str, Any],
) -> str:
    canonical = rag_materialization_canonical_string(
        rag_config_id=rag_config_id,
        chunking_rule_id=chunking_rule_id,
        params=params,
        policy_definition=policy_definition,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
