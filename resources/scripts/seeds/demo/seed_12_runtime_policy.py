from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.governance.schemas.runtime_policy import RuntimePolicyDefinition
from infra.database import get_db
from infra.database.models.governance.runtime_policy import RuntimePolicy

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    RUNTIME_POLICY_TENANT_ID,
    TENANT_DEMO_ID,
    PRINCIPAL_SYSTEM,
)


def _policy_definition() -> dict:
    definition = {
        "limits": {
            "max_nodes": 50,
            "max_depth": 20,
            "max_edges_per_node": 3,
            "max_total_duration_ms": 60000,
            "max_node_duration_ms": 15000,
            "max_loop_iterations": 10,
            "tool_fanout_max_concurrency": 4,
        },
        "execution": {
            "fail_on_multiple_true_edges": True,
            "fail_on_missing_graph": True,
            "allow_parallel_nodes": False,
            "strict_contract_mode": True,
        },
        "tools": {
            "max_retries": 2,
            "circuit_breaker": {
                "failure_threshold": 5,
                "window_seconds": 60,
            },
        },
        "llm": {
            "max_retries": 3,
            "timeout_ms": 30000,
            "stream_enabled": True,
            "stream_eligible_tasks": [
                "response_render",
                "clarification",
            ],
            "history_enabled_tasks": [
                "intent_selection",
                "tool_selection",
                "slot_filling",
                "clarification",
                "response_render",
            ],
            "temperature": 0,
            "max_tokens": 1024,
            "inference_layers": {
                "cache_enabled": True,
                "cache_similarity_threshold": 0.95,
                "cache_ttl_seconds": 3600,
                "slm_enabled": True,
                "slm_eligible_tasks": [
                    "intent_selection",
                    "tool_selection",
                    "fallback_response"
                ],
                "slm_provider": "SLM_LOCAL",
                "slm_model_alias": "qwen2.5-1.5b-instruct",
                "escalation_on_schema_mismatch": True,
            },
        },
        "moderation": {
            "primary": {
                "provider": "SLM_LOCAL",
                "model_alias": "slm-local-moderation",
                "timeout_ms": 300,
            },
            "fallback": {
                "provider": "OPENAI",
                "model_alias": "omni-moderation-latest",
                "timeout_ms": 1000,
            },
            "fallback_enabled": True,
            "prompt_key": "ContentModeration",
            "temperature": 0.0,
            "max_tokens": 18,
        },
        "fallback_sla": {
            "primary": {
                "provider": "SLM_LOCAL",
                "model_alias": "slm-local-moderation",
                "timeout_ms": 300,
            },
            "fallback_enabled": False,
            "prompt_key": "HumanFallback",
            "temperature": 0.0,
            "max_tokens": 100,
        },
        "user_context_enrichment": {
            "enabled": False,
            "gating": False,
            "default_layers_when_published": {
                "allow_tenant_knowledge": True,
                "allow_user_memory_structured": True,
                "allow_user_memory_vector": True,
            },
        },
        "memory_extraction": {
            "enabled": True,
            "rag_config_id": str(RAG_CONFIG_DEMO_ID),
            "preference_schema_id": "user.preference.v1",
            "profile_schema_id": "user.profile_signal.v1",
            "llm": {
                "provider": "OPENAI",
                "model_alias": "gpt-4o-mini",
                "prompt": "Extract user preferences from flow output.",
                "task_type": "MEMORY_EXTRACTION",
            },
        },
        "memory_retrieval": {
            "temporal_scoring": {
                "enabled": False,
                "half_life_seconds": 604800,
                "timestamp_source": "OBSERVED_AT",
                "candidate_multiplier": 3,
            },
        },
    }
    return RuntimePolicyDefinition.model_validate(definition).model_dump(mode="json")


async def seed_runtime_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(RuntimePolicy).where(
                RuntimePolicy.runtime_policy_id == RUNTIME_POLICY_TENANT_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            runtime_policy = RuntimePolicy(
                runtime_policy_id=RUNTIME_POLICY_TENANT_ID,
                tenant_id=TENANT_DEMO_ID,
                scope="TENANT",
                flow_id=None,
                version="1",
                status="ACTIVE",
                policy_definition=_policy_definition(),
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(runtime_policy)
        else:
            existing.policy_definition = _policy_definition()
            session.add(existing)

        await session.commit()
