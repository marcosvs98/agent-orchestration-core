from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select
from pydantic import BaseModel

from infra.database import get_db
from infra.database.models.flow.node import Node
from infra.database.models.flow.node_template import NodeTemplate

from seeds.demo.ids import (
    FLOW_VERSION_V1_ID,
    NODE_CLARIFICATION_ID,
    NODE_CLARIFICATION_INTENT_ID,
    NODE_FALLBACK_SLA_ID,
    NODE_INPUT_MODERATION_ID,
    NODE_INTENT_ID,
    NODE_PRE_EXEC_VALIDATION_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_ERROR_HANDLER_ID,
    NODE_TOOL_EXEC_ID,
    NODE_TOOL_SELECTION_ID,
    NODE_USER_CONTEXT_ENRICHMENT_ID,
    PROMPT_CLARIFICATION_ID,
    PROMPT_FALLBACK_SLA_ID,
    PROMPT_INPUT_MODERATION_ID,
    PROMPT_INTENT_ID,
    PROMPT_RESPONSE_ID,
    PROMPT_SLOT_ID,
    PROMPT_TOOL_SELECTION_ID,
)


class _LlmNodeConfig(BaseModel):
    task_type: str
    provider: str
    model_alias: str
    temperature: float
    top_p: float
    use_system_prompt: bool = True
    use_system_context: bool = True
    max_tokens: int | None = None
    completion_budget: dict[str, float] | None = None
    use_conversation_history: bool | None = None


class _ConfigWithLlm(BaseModel):
    llm: _LlmNodeConfig


class _UserContextLayersConfig(BaseModel):
    allow_tenant_knowledge: bool
    allow_user_memory_structured: bool
    allow_user_memory_vector: bool


class _UserContextNodeConfig(BaseModel):
    publish: bool
    layers: _UserContextLayersConfig


class _ModerationProviderConfig(BaseModel):
    provider: str
    model_alias: str
    timeout_ms: int


class _ModerationNodeConfig(BaseModel):
    primary: _ModerationProviderConfig
    fallback: _ModerationProviderConfig
    fallback_enabled: bool
    prompt_key: str
    temperature: float
    max_tokens: int


def _llm_node_config(
    *,
    task_type: str,
    provider: str,
    model_alias: str,
    temperature: float,
    top_p: float,
    use_system_prompt: bool = True,
    use_system_context: bool = True,
    max_tokens: int | None = None,
    completion_budget: dict[str, float] | None = None,
    use_conversation_history: bool | None = None,
) -> dict[str, object]:
    return _ConfigWithLlm(
        llm=_LlmNodeConfig(
            task_type=task_type,
            provider=provider,
            model_alias=model_alias,
            temperature=temperature,
            top_p=top_p,
            use_system_prompt=use_system_prompt,
            use_system_context=use_system_context,
            max_tokens=max_tokens,
            completion_budget=completion_budget,
            use_conversation_history=use_conversation_history,
        )
    ).model_dump(mode="json")


def _user_context_node_config() -> dict[str, object]:
    return _UserContextNodeConfig(
        publish=True,
        layers=_UserContextLayersConfig(
            allow_tenant_knowledge=True,
            allow_user_memory_structured=True,
            allow_user_memory_vector=True,
        ),
    ).model_dump(mode="json")


def _moderation_node_config() -> dict[str, object]:
    return _ModerationNodeConfig(
        primary=_ModerationProviderConfig(
            provider="SLM_LOCAL",
            model_alias="slm-local-moderation",
            timeout_ms=300,
        ),
        fallback=_ModerationProviderConfig(
            provider="OPENAI",
            model_alias="omni-moderation-latest",
            timeout_ms=1000,
        ),
        fallback_enabled=True,
        prompt_key="InputModerationNode",
        temperature=0.0,
        max_tokens=18,
    ).model_dump(mode="json")


async def seed_nodes() -> None:
    async with get_db() as session:
        templates = [
            (
                "catalog.input_moderation.v1",
                "InputModerationNode",
                _moderation_node_config(),
            ),
            (
                "catalog.user_context_enrichment.v1",
                "UserContextEnrichmentNode",
                _user_context_node_config(),
            ),
            (
                "catalog.intent_detection.v1",
                "IntentDetectionNode",
                _llm_node_config(
                    task_type="INTENT_SELECTION",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.0,
                    top_p=0.05,
                    use_system_prompt=False,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 32,
                    },
                ),
            ),
            (
                "catalog.tool_selection.v1",
                "ToolSelectionNode",
                _llm_node_config(
                    task_type="TOOL_SELECTION",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.0,
                    top_p=0.1,
                    use_system_prompt=False,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 48,
                    },
                ),
            ),
            (
                "catalog.param_extraction.v1",
                "ParamExtractionNode",
                _llm_node_config(
                    task_type="SLOT_FILLING",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.2,
                    top_p=0.2,
                    use_system_prompt=False,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.5,
                        "safety_margin": 24,
                        "floor": 64,
                    },
                ),
            ),
            (
                "catalog.clarification.v1",
                "ClarificationNode",
                _llm_node_config(
                    task_type="CLARIFICATION",
                    provider="OPENAI",
                    model_alias="gpt-4o",
                    temperature=0.3,
                    top_p=0.4,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.7,
                        "safety_margin": 24,
                        "floor": 80,
                    },
                ),
            ),
            ("catalog.tool_execution.v1", "ToolExecutionNode", {}),
            ("catalog.tool_error_handler.v1", "ToolErrorHandlerNode", {"max_retries": 1}),
            (
                "catalog.fallback_sla.v1",
                "FallbackNodeSLA",
                _llm_node_config(
                    task_type="FALLBACK_SLA",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    use_system_prompt=False,
                    use_system_context=False,
                    temperature=0.0,
                    top_p=0.0,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 32,
                    },
                ),
            ),
            (
                "catalog.response_composer.v1",
                "ResponseComposer",
                _llm_node_config(
                    task_type="RESPONSE_RENDER",
                    provider="OPENAI",
                    model_alias="gpt-4o",
                    temperature=0.3,
                    top_p=0.4,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.7,
                        "safety_margin": 24,
                        "floor": 80,
                    },
                ),
            ),
        ]

        for code, node_type, default_config in templates:
            result = await session.execute(
                select(NodeTemplate).where(NodeTemplate.code == code)
            )
            existing_template = result.scalar_one_or_none()
            if existing_template is None:
                template = NodeTemplate(
                    code=code,
                    node_type=node_type,
                    default_config=default_config,
                    scope="system",
                    owner_tenant_id=None,
                    is_active=True,
                )
                session.add(template)
            else:
                existing_template.node_type = node_type
                existing_template.default_config = default_config
                existing_template.scope = "system"
                existing_template.owner_tenant_id = None
                existing_template.is_active = True

        code_to_template: dict[str, NodeTemplate] = {}
        result = await session.execute(
            select(NodeTemplate).where(
                NodeTemplate.scope == "system",
                NodeTemplate.owner_tenant_id.is_(None),
                NodeTemplate.is_active.is_(True),
            )
        )
        for template in result.scalars().all():
            code_to_template[template.code] = template

        node_templates: list[tuple[object, NodeTemplate | None, dict[str, object] | None]] = [
            (
                NODE_INPUT_MODERATION_ID,
                code_to_template.get("catalog.input_moderation.v1"),
                _moderation_node_config(),
            ),
            (
                NODE_USER_CONTEXT_ENRICHMENT_ID,
                code_to_template.get("catalog.user_context_enrichment.v1"),
                _user_context_node_config(),
            ),
            (
                NODE_INTENT_ID,
                code_to_template.get("catalog.intent_detection.v1"),
                _llm_node_config(
                    task_type="INTENT_SELECTION",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.0,
                    top_p=0.05,
                    use_system_prompt=False,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 32,
                    },
                ),
            ),
            (
                NODE_CLARIFICATION_INTENT_ID,
                code_to_template.get("catalog.clarification.v1"),
                _llm_node_config(
                    task_type="CLARIFICATION",
                    provider="OPENAI",
                    model_alias="gpt-4o",
                    temperature=0.3,
                    top_p=0.4,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.7,
                        "safety_margin": 24,
                        "floor": 80,
                    },
                ),
            ),
            (
                NODE_TOOL_SELECTION_ID,
                code_to_template.get("catalog.tool_selection.v1"),
                _llm_node_config(
                    task_type="TOOL_SELECTION",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.0,
                    top_p=0.1,
                    use_system_prompt=False,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 48,
                    },
                ),
            ),
            (
                NODE_SLOT_ID,
                code_to_template.get("catalog.param_extraction.v1"),
                _llm_node_config(
                    task_type="SLOT_FILLING",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    temperature=0.2,
                    top_p=0.2,
                    use_system_prompt=False,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.5,
                        "safety_margin": 24,
                        "floor": 64,
                    },
                ),
            ),
            (
                NODE_CLARIFICATION_ID,
                code_to_template.get("catalog.clarification.v1"),
                _llm_node_config(
                    task_type="CLARIFICATION",
                    provider="OPENAI",
                    model_alias="gpt-4o",
                    temperature=0.3,
                    top_p=0.4,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.7,
                        "safety_margin": 24,
                        "floor": 80,
                    },
                ),
            ),
            (
                NODE_TOOL_EXEC_ID,
                code_to_template.get("catalog.tool_execution.v1"),
                {},
            ),
            (
                NODE_TOOL_ERROR_HANDLER_ID,
                code_to_template.get("catalog.tool_error_handler.v1"),
                {"max_retries": 1},
            ),
            (
                NODE_FALLBACK_SLA_ID,
                code_to_template.get("catalog.fallback_sla.v1"),
                _llm_node_config(
                    task_type="FALLBACK_SLA",
                    provider="OPENAI",
                    model_alias="gpt-4.1-mini",
                    use_system_prompt=False,
                    use_system_context=False,
                    temperature=0.0,
                    top_p=0.0,
                    use_conversation_history=False,
                    completion_budget={
                        "schema_factor": 1.2,
                        "safety_margin": 16,
                        "floor": 32,
                    },
                ),
            ),
            (
                NODE_RESPONSE_ID,
                code_to_template.get("catalog.response_composer.v1"),
                _llm_node_config(
                    task_type="RESPONSE_RENDER",
                    provider="OPENAI",
                    model_alias="gpt-4o",
                    temperature=0.3,
                    top_p=0.4,
                    use_conversation_history=True,
                    completion_budget={
                        "schema_factor": 1.7,
                        "safety_margin": 24,
                        "floor": 80,
                    },
                ),
            ),
        ]

        node_prompt_map: dict[object, object] = {
            NODE_INPUT_MODERATION_ID: PROMPT_INPUT_MODERATION_ID,
            NODE_USER_CONTEXT_ENRICHMENT_ID: PROMPT_RESPONSE_ID,
            NODE_INTENT_ID: PROMPT_INTENT_ID,
            NODE_CLARIFICATION_INTENT_ID: PROMPT_CLARIFICATION_ID,
            NODE_TOOL_SELECTION_ID: PROMPT_TOOL_SELECTION_ID,
            NODE_SLOT_ID: PROMPT_SLOT_ID,
            NODE_PRE_EXEC_VALIDATION_ID: PROMPT_RESPONSE_ID,
            NODE_TOOL_EXEC_ID: PROMPT_RESPONSE_ID,
            NODE_TOOL_ERROR_HANDLER_ID: PROMPT_RESPONSE_ID,
            NODE_RESPONSE_ID: PROMPT_RESPONSE_ID,
            NODE_CLARIFICATION_ID: PROMPT_CLARIFICATION_ID,
            NODE_FALLBACK_SLA_ID: PROMPT_FALLBACK_SLA_ID,
        }

        node_flags: dict[object, tuple[bool, bool, bool, bool]] = {
            NODE_INPUT_MODERATION_ID: (False, False, False, False),
            NODE_USER_CONTEXT_ENRICHMENT_ID: (False, False, False, False),
            NODE_INTENT_ID: (False, False, False, False),
            NODE_CLARIFICATION_INTENT_ID: (False, False, False, False),
            NODE_TOOL_SELECTION_ID: (False, False, False, False),
            NODE_SLOT_ID: (False, False, False, False),
            NODE_PRE_EXEC_VALIDATION_ID: (False, False, False, False),
            NODE_TOOL_EXEC_ID: (False, False, False, False),
            NODE_TOOL_ERROR_HANDLER_ID: (False, False, False, False),
            NODE_RESPONSE_ID: (True, True, True, True),
            NODE_CLARIFICATION_ID: (False, False, False, False),
            NODE_FALLBACK_SLA_ID: (False, False, False, False),
        }

        for raw_node_id, template, override_config in node_templates:
            node_uuid = raw_node_id
            result = await session.execute(
                select(Node).where(Node.node_id == node_uuid)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                continue
            node_type = template.node_type if template is not None else None
            base_config: dict[str, object] = (
                template.default_config if template is not None else {}
            )
            overrides: dict[str, object] = override_config or {}
            effective_config = {**base_config, **overrides} if node_type else None
            node_prompt_id = node_prompt_map[raw_node_id]
            (
                allow_rag_tenant,
                allow_user_memory,
                allow_session_context,
                allow_memory_write,
            ) = node_flags[raw_node_id]
            node = Node(
                node_id=node_uuid,
                flow_version_id=FLOW_VERSION_V1_ID,
                node_prompt_id=node_prompt_id,
                allow_rag_tenant=allow_rag_tenant,
                allow_user_memory=allow_user_memory,
                allow_session_context=allow_session_context,
                allow_memory_write=allow_memory_write,
                node_type=node_type,
                config=effective_config,
                source_node_template_id=(
                    template.node_template_id if template is not None else None
                ),
            )
            session.add(node)

        await session.commit()
