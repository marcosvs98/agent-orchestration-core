from __future__ import annotations

import uuid

import pytest

from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge, FlowGraphNodeSpec
from domain.flows.services.flow_graph_validator import FlowGraphValidator
from exceptions.service_exceptions import DomainValidationException


def _minimal_graph(*, extra_memory_commit: bool) -> FlowGraphDefinition:
    rid = str(uuid.uuid4())
    mc2: dict[str, FlowGraphNodeSpec] = {}
    edges_extra: list[FlowGraphEdge] = []
    if extra_memory_commit:
        mc2["m2"] = FlowGraphNodeSpec(
            type="MemoryCommitNode",
            config={"schema_id": "user.preference.v1", "rag_config_id": rid},
        )
        edges_extra = [
            FlowGraphEdge(
                from_node="x",
                to_node="m2",
                condition="1==1",
            ),
            FlowGraphEdge(
                from_node="m2",
                to_node="t",
                condition="1==1",
            ),
        ]
    nodes = {
        "s": FlowGraphNodeSpec(type="ContentModeration", config={}),
        "x": FlowGraphNodeSpec(type="IntentClassifier", config={}),
        "m1": FlowGraphNodeSpec(
            type="MemoryCommitNode",
            config={"schema_id": "user.preference.v1", "rag_config_id": rid},
        ),
        "t": FlowGraphNodeSpec(type="ResponseBuilder", config={}),
        **mc2,
    }
    edges = [
        FlowGraphEdge(from_node="s", to_node="x", condition="1==1"),
        FlowGraphEdge(from_node="x", to_node="m1", condition="1==1"),
        FlowGraphEdge(from_node="m1", to_node="t", condition="1==1"),
        *edges_extra,
    ]
    return FlowGraphDefinition(start_node="s", nodes=nodes, edges=edges)


def test_flow_graph_validator_allows_single_memory_commit() -> None:
    FlowGraphValidator.validate(_minimal_graph(extra_memory_commit=False))


def test_flow_graph_validator_rejects_multiple_memory_commits() -> None:
    with pytest.raises(DomainValidationException) as exc:
        FlowGraphValidator.validate(_minimal_graph(extra_memory_commit=True))
    assert exc.value.message == "multiple_memory_commit_nodes"


def test_flow_graph_validator_rejects_deprecated_user_context_enrichment_node() -> None:
    nodes = {
        "s": FlowGraphNodeSpec(type="ContentModeration", config={}),
        "u": FlowGraphNodeSpec(
            type="UserContextEnrichmentNode",
            config={"publish": True, "layers": {}},
        ),
        "t": FlowGraphNodeSpec(type="ResponseBuilder", config={}),
    }
    edges = [
        FlowGraphEdge(from_node="s", to_node="u", condition="1==1"),
        FlowGraphEdge(from_node="u", to_node="t", condition="1==1"),
    ]
    definition = FlowGraphDefinition(start_node="s", nodes=nodes, edges=edges)
    with pytest.raises(DomainValidationException) as exc:
        FlowGraphValidator.validate(definition)
    assert exc.value.message == "deprecated_node_type_user_context_enrichment"


def test_flow_graph_validator_rejects_memory_commit_data_merge_unknown_from_node() -> None:
    rid = str(uuid.uuid4())
    nodes = {
        "s": FlowGraphNodeSpec(type="ContentModeration", config={}),
        "m": FlowGraphNodeSpec(
            type="MemoryCommitNode",
            config={
                "schema_id": "user.preference.v1",
                "rag_config_id": rid,
                "data_merge": [
                    {
                        "from_node_id": "nonexistent-node-id",
                        "path": "x",
                        "target_key": "y",
                    }
                ],
            },
        ),
        "t": FlowGraphNodeSpec(type="ResponseBuilder", config={}),
    }
    edges = [
        FlowGraphEdge(from_node="s", to_node="m", condition="1==1"),
        FlowGraphEdge(from_node="m", to_node="t", condition="1==1"),
    ]
    definition = FlowGraphDefinition(start_node="s", nodes=nodes, edges=edges)
    with pytest.raises(DomainValidationException) as exc:
        FlowGraphValidator.validate(definition)
    assert exc.value.message == "memory_commit_data_merge_unknown_from_node"


def test_flow_graph_validator_rejects_rag_pipeline_non_dict() -> None:
    nodes = {
        "s": FlowGraphNodeSpec(type="ContentModeration", config={}),
        "x": FlowGraphNodeSpec(
            type="IntentClassifier",
            config={"rag_pipeline": ["invalid"]},
        ),
        "t": FlowGraphNodeSpec(type="ResponseBuilder", config={}),
    }
    edges = [
        FlowGraphEdge(from_node="s", to_node="x", condition="1==1"),
        FlowGraphEdge(from_node="x", to_node="t", condition="1==1"),
    ]
    definition = FlowGraphDefinition(start_node="s", nodes=nodes, edges=edges)
    with pytest.raises(DomainValidationException) as exc:
        FlowGraphValidator.validate(definition)
    assert exc.value.message == "rag_pipeline_config_invalid"
