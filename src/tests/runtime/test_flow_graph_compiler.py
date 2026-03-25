import uuid

import pytest

from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge, FlowGraphNodeSpec
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler
from domain.flows.services.flow_graph_draft_validator import FlowGraphDraftValidator
from exceptions.service_exceptions import DomainValidationException


def _base_definition():
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    return FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )


def test_compiler_is_deterministic():
    compiler = FlowGraphCompiler()
    definition = _base_definition()
    snapshot1, hash1 = compiler.compile(definition)
    snapshot2, hash2 = compiler.compile(definition)
    assert snapshot1 == snapshot2
    assert hash1 == hash2
    edge = snapshot1["edges"][0]
    assert edge["compiled_condition"]["type"] in {"compare", "bool_op"}


def test_validator_rejects_duplicate_conditions():
    definition = _base_definition()
    node_c = str(uuid.uuid4())
    definition.nodes[node_c] = FlowGraphNodeSpec(type="ResponseBuilder")
    definition.edges.append(
        FlowGraphEdge(from_node=definition.start_node, to_node=node_c, condition="1 == 1")
    )
    with pytest.raises(DomainValidationException):
        FlowGraphDraftValidator.validate(definition)


def test_validator_rejects_unmarked_cycle():
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1"),
            FlowGraphEdge(from_node=node_b, to_node=node_a, condition="1 == 1"),
        ],
    )
    with pytest.raises(DomainValidationException):
        FlowGraphDraftValidator.validate(definition)


def test_validator_allows_marked_loop():
    node_a = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={node_a: FlowGraphNodeSpec(type="ResponseBuilder")},
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_a, condition="1 == 1", edge_kind="LOOP"),
        ],
    )
    FlowGraphDraftValidator.validate(definition)
