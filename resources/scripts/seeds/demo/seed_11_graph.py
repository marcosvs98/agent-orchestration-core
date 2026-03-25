from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select, update
from pydantic import BaseModel

from domain.common.schemas.versioning import VersionStatus
from domain.flows.schemas.graph import (
    EdgeKind,
    FlowGraphDefinition,
    FlowGraphEdge,
    FlowGraphNodeSpec,
)
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler
from domain.flows.services.flow_graph_draft_validator import FlowGraphDraftValidator
from infra.database import get_db
from infra.database.models.flow.flow_graph_draft import FlowGraphDraft
from infra.database.models.flow.flow_graph_snapshot import FlowGraphSnapshot
from infra.database.models.flow.flow_version import FlowVersion

from seeds.demo.ids import (
    FLOW_DEMO_ID,
    FLOW_GRAPH_DRAFT_ID,
    FLOW_GRAPH_SNAPSHOT_ID,
    FLOW_VERSION_V1_ID,
    NODE_CLARIFICATION_ID,
    NODE_FALLBACK_SLA_ID,
    NODE_INPUT_MODERATION_ID,
    NODE_MEMORY_COMMIT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_ERROR_HANDLER_ID,
    NODE_TOOL_EXEC_ID,
    NODE_TOOL_SELECTION_ID,
    NODE_MEMORY_PAYLOAD_SUMMARIZE_ID,
    PRINCIPAL_SYSTEM,
    RAG_CONFIG_DEMO_ID,
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


class _ResumeConfigWithLlm(BaseModel):
    resume_to_node_id: str
    llm: _LlmNodeConfig


class _ModerationProviderConfig(BaseModel):
    provider: str
    model_alias: str
    timeout_ms: int


class _MemoryCommitNodeConfig(BaseModel):
    schema_id: str
    schema_version: int = 1
    source: str = "explicit_user"
    rag_config_id: str
    data: dict[str, object] | None = None
    data_merge: list[dict[str, object]] | None = None


class _ModerationNodeConfig(BaseModel):
    primary: _ModerationProviderConfig = _ModerationProviderConfig(
        provider="SLM_LOCAL",
        model_alias="slm-local-moderation",
        timeout_ms=300,
    )
    fallback: _ModerationProviderConfig = _ModerationProviderConfig(
        provider="OPENAI",
        model_alias="omni-moderation-latest",
        timeout_ms=1000,
    )
    fallback_enabled: bool = True
    prompt_key: str = "ContentModeration"
    temperature: float = 0.0
    max_tokens: int = 18


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


def _resume_llm_node_config(
    *,
    resume_to_node_id: str,
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
    return _ResumeConfigWithLlm(
        resume_to_node_id=resume_to_node_id,
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
        ),
    ).model_dump(mode="json")


def _memory_payload_summarize_node_config() -> dict[str, object]:
    base = _llm_node_config(
        task_type="MEMORY_CONTENT_SUMMARIZE",
        provider="OPENAI",
        model_alias="gpt-4.1-mini",
        temperature=0.0,
        top_p=0.0,
        use_system_prompt=False,
        use_system_context=False,
        use_conversation_history=False,
        completion_budget={
            "schema_factor": 1.2,
            "safety_margin": 16,
            "floor": 48,
        },
    )
    return {
        "source_node_id": str(NODE_SLOT_ID),
        "min_payload_bytes_to_run": 4096,
        **base,
    }


def _moderation_node_config() -> dict[str, object]:
    return _ModerationNodeConfig().model_dump(mode="json")


def _tool_resolver_demo_config() -> dict[str, object]:
    base = _llm_node_config(
        task_type="TOOL_SELECTION",
        provider="OPENAI",
        model_alias="gpt-4.1-mini",
        temperature=0,
        top_p=0.1,
        use_system_prompt=False,
        use_conversation_history=False,
        completion_budget={
            "schema_factor": 1.2,
            "safety_margin": 16,
            "floor": 48,
        },
    )
    base["confidence_threshold"] = 0.78
    base["top_k"] = 10
    return base


def _memory_commit_node_config() -> dict[str, object]:
    return _MemoryCommitNodeConfig(
        schema_id="user.preference.v1",
        schema_version=1,
        source="explicit_user",
        rag_config_id=str(RAG_CONFIG_DEMO_ID),
        data={
            "preference_key": "demo.memory_commit",
            "preference_value": "graph_seed",
        },
        data_merge=[
            {
                "from_node_id": str(NODE_SLOT_ID),
                "path": "result.0.params.nickname",
                "target_key": "nickname",
            },
            {
                "from_node_id": str(NODE_SLOT_ID),
                "path": "result.0.params.financial_goal",
                "target_key": "financial_goal",
            },
            {
                "from_node_id": str(NODE_MEMORY_PAYLOAD_SUMMARIZE_ID),
                "path": "prepared_memory_data",
                "target_key": "summarized_slot_snapshot",
            },
        ],
    ).model_dump(mode="json")


async def seed_graph() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(FlowVersion).where(
                FlowVersion.flow_version_id == FLOW_VERSION_V1_ID
            )
        )
        flow_version = result.scalar_one_or_none()
        if flow_version is None:
            raise ValueError(
                f"FlowVersion {FLOW_VERSION_V1_ID} não encontrado. Execute seed_07_flow primeiro."
            )

        definition = FlowGraphDefinition(
            start_node=str(NODE_INPUT_MODERATION_ID),
            nodes={
                str(NODE_INPUT_MODERATION_ID): FlowGraphNodeSpec(
                    type="ContentModeration",
                    config=_moderation_node_config(),
                ),
                str(NODE_MEMORY_PAYLOAD_SUMMARIZE_ID): FlowGraphNodeSpec(
                    type="ContextSummarizer",
                    config=_memory_payload_summarize_node_config(),
                ),
                str(NODE_TOOL_SELECTION_ID): FlowGraphNodeSpec(
                    type="ToolResolver",
                    config=_tool_resolver_demo_config(),
                ),
                str(NODE_SLOT_ID): FlowGraphNodeSpec(
                    type="ToolInputFiller",
                    config=_llm_node_config(
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
                str(NODE_CLARIFICATION_ID): FlowGraphNodeSpec(
                    type="QueryClarifier",
                    config=_resume_llm_node_config(
                        resume_to_node_id=str(NODE_SLOT_ID),
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
                str(NODE_TOOL_EXEC_ID): FlowGraphNodeSpec(
                    type="ToolExecutor",
                    config={},
                ),
                str(NODE_TOOL_ERROR_HANDLER_ID): FlowGraphNodeSpec(
                    type="ToolErrorHandlerNode",
                    config={"max_retries": 1},
                ),
                str(NODE_FALLBACK_SLA_ID): FlowGraphNodeSpec(
                    type="HumanFallback",
                    config=_llm_node_config(
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
                    )
                ),
                str(NODE_MEMORY_COMMIT_ID): FlowGraphNodeSpec(
                    type="MemoryCommitNode",
                    config=_memory_commit_node_config(),
                ),
                str(NODE_RESPONSE_ID): FlowGraphNodeSpec(
                    type="ResponseBuilder",
                    config=_llm_node_config(
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
            },
            edges=[
                FlowGraphEdge(
                    from_node=str(NODE_INPUT_MODERATION_ID),
                    to_node=str(NODE_TOOL_SELECTION_ID),
                    condition="flagged == false",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INPUT_MODERATION_ID),
                    to_node=str(NODE_FALLBACK_SLA_ID),
                    condition="flagged == true",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_SELECTION_ID),
                    to_node=str(NODE_SLOT_ID),
                    condition="len(result) >= 1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_SELECTION_ID),
                    to_node=str(NODE_MEMORY_COMMIT_ID),
                    condition="len(result) < 1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_SLOT_ID),
                    to_node=str(NODE_CLARIFICATION_ID),
                    condition="HasAny(result.status, ['incomplete'])",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_CLARIFICATION_ID),
                    to_node=str(NODE_SLOT_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.LOOP,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_SLOT_ID),
                    to_node=str(NODE_TOOL_EXEC_ID),
                    condition="HasAll(result.status, ['ready'])",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_EXEC_ID),
                    to_node=str(NODE_MEMORY_PAYLOAD_SUMMARIZE_ID),
                    condition="HasAll(result.status, ['success', 'scheduled'])",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_MEMORY_PAYLOAD_SUMMARIZE_ID),
                    to_node=str(NODE_MEMORY_COMMIT_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_EXEC_ID),
                    to_node=str(NODE_TOOL_ERROR_HANDLER_ID),
                    condition="HasAny(result.status, ['incomplete', 'error', 'cancelled'])",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_ERROR_HANDLER_ID),
                    to_node=str(NODE_TOOL_EXEC_ID),
                    condition="retry_operation_ids_count > 0",
                    edge_kind=EdgeKind.LOOP,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_ERROR_HANDLER_ID),
                    to_node=str(NODE_FALLBACK_SLA_ID),
                    condition="fallback_required == true",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_ERROR_HANDLER_ID),
                    to_node=str(NODE_MEMORY_COMMIT_ID),
                    condition="retry_operation_ids_count == 0 and fallback_required == false",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_FALLBACK_SLA_ID),
                    to_node=str(NODE_MEMORY_COMMIT_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_MEMORY_COMMIT_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.NORMAL,
                ),
            ],
        )

        validator = FlowGraphDraftValidator()
        validator.validate(definition)

        result = await session.execute(
            select(FlowGraphDraft).where(
                FlowGraphDraft.flow_version_id == FLOW_VERSION_V1_ID
            )
        )
        draft = result.scalar_one_or_none()

        if draft is None:
            definition_dict = {
                "start_node": definition.start_node,
                "nodes": {
                    k: v.model_dump() for k, v in definition.nodes.items()
                },
                "edges": [e.model_dump() for e in definition.edges],
            }
            draft = FlowGraphDraft(
                flow_graph_draft_id=FLOW_GRAPH_DRAFT_ID,
                flow_version_id=FLOW_VERSION_V1_ID,
                definition=definition_dict,
                status="DRAFT",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(draft)
            await session.commit()

        result = await session.execute(
            select(FlowGraphSnapshot).where(
                FlowGraphSnapshot.flow_version_id == FLOW_VERSION_V1_ID
            )
        )
        snapshot = result.scalar_one_or_none()

        compiler = FlowGraphCompiler()
        compiled_snapshot, graph_hash = compiler.compile(definition)

        if snapshot is None:
            snapshot = FlowGraphSnapshot(
                flow_graph_snapshot_id=FLOW_GRAPH_SNAPSHOT_ID,
                flow_version_id=FLOW_VERSION_V1_ID,
                graph_hash=graph_hash,
                snapshot=compiled_snapshot,
                compiled_by=PRINCIPAL_SYSTEM,
            )
            session.add(snapshot)
        else:
            snapshot.graph_hash = graph_hash
            snapshot.snapshot = compiled_snapshot
        await session.commit()

        if flow_version.status != VersionStatus.PUBLISHED.value:
            flow_version.status = VersionStatus.PUBLISHED.value
            await session.commit()

        await session.execute(
            update(FlowVersion)
            .where(
                FlowVersion.flow_id == FLOW_DEMO_ID,
                FlowVersion.flow_version_id != FLOW_VERSION_V1_ID,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(FlowVersion)
            .where(
                FlowVersion.flow_id == FLOW_DEMO_ID,
                FlowVersion.flow_version_id == FLOW_VERSION_V1_ID,
            )
            .values(
                is_active=True,
                activated_at=datetime.now(timezone.utc),
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="Bootstrap seed - ativação inicial",
            )
        )
        await session.commit()
