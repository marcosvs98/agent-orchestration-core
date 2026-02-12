from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

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
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_EXEC_ID,
    NODE_USER_CONTEXT_ENRICHMENT_ID,
    PRINCIPAL_SYSTEM,
)


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
                    config={
                        "publish": True,
                        "layers": {
                            "allow_tenant_knowledge": True,
                            "allow_user_memory_structured": True,
                            "allow_user_memory_vector": True,
                        },
                    },
                ),
                str(NODE_INTENT_ID): FlowGraphNodeSpec(
                    type="IntentToolSelectionNode",
                    config={
                        "llm": {
                            "task_type": "INTENT_SELECTION",
                            "provider": "OPENAI",
                            "model_alias": "fake-model",
                            "input": {},
                            "input_schema": {},
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "intent": {"type": ["string", "null"]},
                                    "tool_config_id": {
                                        "type": ["string", "null"],
                                        "format": "uuid",
                                    },
                                    "clarification": {"type": "boolean"},
                                    "intent_category": {
                                        "type": "string",
                                        "enum": ["TRANSACTION", "DECLARATION", "SMALL_TALK"],
                                    },
                                },
                                "required": ["intent", "tool_config_id", "clarification"],
                            },
                        },
                        "default_tool_config_id": "00000000-0000-0000-0000-000000000501",
                    },
                ),
                    str(NODE_SLOT_ID): FlowGraphNodeSpec(
                        type="ParamExtractionNode",
                        config={
                            "llm": {
                                "task_type": "SLOT_FILLING",
                                "provider": "OPENAI",
                                "model_alias": "fake-model",
                                "input": {},
                                "input_schema": {},
                                "output_schema": {
                                    "type": "object",
                                "required": [
                                    "payload",
                                    "missing_fields",
                                    "missing_fields_count",
                                    "execution_ready",
                                ],
                                    "properties": {
                                        "payload": {
                                        "type": "object"
                                        },
                                        "missing_fields": {
                                        "type": "array",
                                        "items": { "type": "string" }
                                    },
                                    "missing_fields_count": {
                                    "type": "integer"
                                    },
                                    "execution_ready": {
                                    "type": "boolean"
                                        }
                                    }
                                },
                            }
                        },
                    ),
                str(NODE_CLARIFICATION_ID): FlowGraphNodeSpec(
                    type="ClarificationNode",
                    config={
                        "resume_to_node_id": str(NODE_SLOT_ID),
                        "llm": {
                            "task_type": "CLARIFICATION",
                            "provider": "OPENAI",
                            "model_alias": "fake-model",
                            "input": {},
                            "input_schema": {},
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "system_output": {"type": "string"},
                                },
                                "required": ["system_output"],
                            },
                        },
                    },
                ),
                str(NODE_TOOL_EXEC_ID): FlowGraphNodeSpec(
                    type="ToolExecutionNode", config={}
                ),
                str(NODE_RESPONSE_ID): FlowGraphNodeSpec(
                    type="ResponseNode",
                    config={
                        "llm": {
                            "task_type": "GENERATION",
                            "provider": "OPENAI",
                            "model_alias": "fake-model",
                            "input": {},
                            "input_schema": {},
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "system_output": {"type": "string"},
                                },
                                "required": ["system_output"],
                            },
                        },
                    },
                ),
            },
            edges=[
                FlowGraphEdge(
                    from_node=str(NODE_USER_CONTEXT_ENRICHMENT_ID),
                    to_node=str(NODE_INTENT_ID),
                    condition="true",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INTENT_ID),
                    to_node=str(NODE_SLOT_ID),
                    condition='intent_category == "TRANSACTION"',
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_INTENT_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition='(intent_category == "DECLARATION" or intent_category == "SMALL_TALK")',
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_SLOT_ID),
                    to_node=str(NODE_TOOL_EXEC_ID),
                    condition="missing_fields_count == 0",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_SLOT_ID),
                    to_node=str(NODE_CLARIFICATION_ID),
                    condition="missing_fields_count > 0",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_CLARIFICATION_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition="true",
                    edge_kind=EdgeKind.NORMAL,
                ),
                FlowGraphEdge(
                    from_node=str(NODE_TOOL_EXEC_ID),
                    to_node=str(NODE_RESPONSE_ID),
                    condition="true",
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
