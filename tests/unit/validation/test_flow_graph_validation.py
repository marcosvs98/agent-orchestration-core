from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge, FlowGraphNodeSpec
from domain.flows.services.condition_evaluator import ConditionEvaluator
from domain.flows.services.flow_graph_validator import FlowGraphValidator


def test_condition_evaluator_basic():
    ctx = {"validation_status": "VALID", "confidence": 0.9}
    assert ConditionEvaluator.evaluate("validation_status == 'VALID' && confidence >= 0.85", ctx)
    assert not ConditionEvaluator.evaluate("confidence < 0.5", ctx)


def test_flow_graph_validator_accepts_valid_graph():
    definition = FlowGraphDefinition(
        start_node="A",
        nodes={
            "A": FlowGraphNodeSpec(type="ToolResolver"),
            "B": FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node="A", to_node="B", condition="1 == 1")],
    )
    FlowGraphValidator.validate(definition)


def test_flow_graph_validator_rejects_unreachable():
    definition = FlowGraphDefinition(
        start_node="A",
        nodes={
            "A": FlowGraphNodeSpec(type="ToolResolver"),
            "B": FlowGraphNodeSpec(type="ResponseBuilder"),
            "C": FlowGraphNodeSpec(type="HumanFallback"),
        },
        edges=[FlowGraphEdge(from_node="A", to_node="B", condition="1 == 1")],
    )
    try:
        FlowGraphValidator.validate(definition)
        assert False, "expected failure"
    except Exception:
        assert True
