from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select
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
from infra.database.models.flow.active_flow_version import ActiveFlowVersion
from infra.database.models.flow.flow_version import FlowVersion

from seeds.demo.ids import (
    FLOW_DEMO_ID,
    FLOW_GRAPH_DRAFT_ID,
    FLOW_GRAPH_SNAPSHOT_ID,
    FLOW_VERSION_V1_ID,
    NODE_CLARIFICATION_ID,
    NODE_CLARIFICATION_INTENT_ID,
    NODE_FALLBACK_SLA_ID,
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_ERROR_HANDLER_ID,
    NODE_TOOL_EXEC_ID,
    NODE_TOOL_SELECTION_ID,
    NODE_USER_CONTEXT_ENRICHMENT_ID,
    PRINCIPAL_SYSTEM,
)


class _LlmNodeConfig(BaseModel):
    task_type: str
    provider: str
    model_alias: str
    temperature: float
    top_p: float


class _ConfigWithLlm(BaseModel):
    llm: _LlmNodeConfig


class _ResumeConfigWithLlm(BaseModel):
    resume_to_node_id: str
    llm: _LlmNodeConfig


class _UserContextLayersConfig(BaseModel):
    allow_tenant_knowledge: bool
    allow_user_memory_structured: bool
    allow_user_memory_vector: bool


class _UserContextNodeConfig(BaseModel):
    publish: bool
    layers: _UserContextLayersConfig


def _llm_node_config(
    *,
    task_type: str,
    provider: str,
    model_alias: str,
    temperature: float,
    top_p: float,
) -> dict[str, object]:
    return _ConfigWithLlm(
        llm=_LlmNodeConfig(
            task_type=task_type,
            provider=provider,
            model_alias=model_alias,
            temperature=temperature,
            top_p=top_p,
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
) -> dict[str, object]:
    return _ResumeConfigWithLlm(
        resume_to_node_id=resume_to_node_id,
        llm=_LlmNodeConfig(
            task_type=task_type,
            provider=provider,
            model_alias=model_alias,
            temperature=temperature,
            top_p=top_p,
        ),
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
            start_node=str(NODE_USER_CONTEXT_ENRICHMENT_ID),
            nodes={
                str(NODE_USER_CONTEXT_ENRICHMENT_ID): FlowGraphNodeSpec(
                    type="UserContextEnrichmentNode",
                    config=_user_context_node_config(),
                ),
                str(NODE_INTENT_ID): FlowGraphNodeSpec(
                    type="IntentDetectionNode",
                    config=_llm_node_config(
                        task_type="INTENT_SELECTION",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.1,
                        top_p=0.1,
                    ),
                ),
                str(NODE_TOOL_SELECTION_ID): FlowGraphNodeSpec(
                    type="ToolSelectionNode",
                    config=_llm_node_config(
                        task_type="TOOL_SELECTION",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.1,
                        top_p=0.2,
                    ),
                ),
                str(NODE_SLOT_ID): FlowGraphNodeSpec(
                    type="ParamExtractionNode",
                    config=_llm_node_config(
                        task_type="SLOT_FILLING",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.2,
                        top_p=0.2,
                    ),
                ),
                str(NODE_CLARIFICATION_INTENT_ID): FlowGraphNodeSpec(
                    type="ClarificationNode",
                    config=_resume_llm_node_config(
                        resume_to_node_id=str(NODE_INTENT_ID),
                        task_type="CLARIFICATION",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.4,
                        top_p=0.3,
                    ),
                ),
                str(NODE_CLARIFICATION_ID): FlowGraphNodeSpec(
                    type="ClarificationNode",
                    config=_resume_llm_node_config(
                        resume_to_node_id=str(NODE_SLOT_ID),
                        task_type="CLARIFICATION",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.4,
                        top_p=0.3,
                    ),
                ),
                str(NODE_TOOL_EXEC_ID): FlowGraphNodeSpec(
                    type="ToolExecutionNode",
                    config={},
                ),
                str(NODE_TOOL_ERROR_HANDLER_ID): FlowGraphNodeSpec(
                    type="ToolErrorHandlerNode",
                    config={"max_retries": 1},
                ),
                str(NODE_FALLBACK_SLA_ID): FlowGraphNodeSpec(
                    type="FallbackNode",
                    config={},
                ),
                str(NODE_RESPONSE_ID): FlowGraphNodeSpec(
                    type="ResponseComposer",
                    config=_llm_node_config(
                        task_type="RESPONSE_RENDER",
                        provider="OPENAI",
                        model_alias="gpt-4.1-mini",
                        temperature=0.3,
                        top_p=0.4,
                    ),
                ),
            },
            edges=[
                FlowGraphEdge(
                    from_node=str(NODE_USER_CONTEXT_ENRICHMENT_ID),
                    to_node=str(NODE_INTENT_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INTENT_ID),
                    to_node=str(NODE_CLARIFICATION_INTENT_ID),
                    condition="overall_confidence < 0.6",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INTENT_ID),
                    to_node=str(NODE_TOOL_SELECTION_ID),
                    condition="HasAny(result.intent_type, ['execution', 'query']) and overall_confidence >= 0.8",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INTENT_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition="overall_confidence >= 0.6 and (HasAny(result.intent_type, ['conversation']) or not HasAny(result.intent_type, ['execution', 'query']))",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_CLARIFICATION_INTENT_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition="1==1",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_SELECTION_ID),
                    to_node=str(NODE_SLOT_ID),
                    condition="len(result) >= 1",
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
                    to_node=str(NODE_RESPONSE_ID),
                    condition="HasAll(result.status, ['success', 'scheduled'])",
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
                    to_node=str(NODE_RESPONSE_ID),
                    condition="retry_operation_ids_count == 0 and fallback_required == false",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_FALLBACK_SLA_ID),
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

        result = await session.execute(
            select(ActiveFlowVersion).where(
                ActiveFlowVersion.flow_id == FLOW_DEMO_ID
            )
        )
        active_flow = result.scalar_one_or_none()

        if active_flow is None:
            active_flow = ActiveFlowVersion(
                flow_id=FLOW_DEMO_ID,
                flow_version_id=FLOW_VERSION_V1_ID,
                flow_graph_snapshot_id=FLOW_GRAPH_SNAPSHOT_ID,
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="Bootstrap seed - ativação inicial",
            )
            session.add(active_flow)
            await session.commit()
