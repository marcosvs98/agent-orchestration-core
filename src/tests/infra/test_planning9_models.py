from infra.database.models.flow.router import Router
from infra.database.models.routing.routing_rule import RoutingRule
from infra.database.models.agent.agent_version import AgentVersion
from infra.database.models.execution.agent_run import AgentRun
from infra.database.models.execution.execution_event import ExecutionEvent


def test_router_belongs_to_node():
    assert hasattr(Router, "node_id")


def test_routing_rule_has_from_and_to_node():
    assert hasattr(RoutingRule, "from_node_id")
    assert hasattr(RoutingRule, "to_node_id")


def test_agent_version_links_policy_and_rag():
    assert hasattr(AgentVersion, "ai_execution_policy_version_id")
    assert hasattr(AgentVersion, "rag_config_id")


def test_agent_run_links_policy_version():
    assert hasattr(AgentRun, "ai_execution_policy_version_id")


def test_execution_event_exists():
    assert hasattr(ExecutionEvent, "flow_run_id")
