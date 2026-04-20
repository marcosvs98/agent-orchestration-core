from domain.execution.services.state_machine import RunLifecycleStateMachine


def test_flow_run_transitions_allowed():
    sm = RunLifecycleStateMachine()
    sm.validate_flow("CREATED", "RUNNING")
    sm.validate_flow("RUNNING", "WAITING")
    sm.validate_flow("WAITING", "RUNNING")
    sm.validate_flow("RUNNING", "COMPLETED")


def test_node_run_transitions_allowed():
    sm = RunLifecycleStateMachine()
    sm.validate_node("PENDING", "RUNNING")
    sm.validate_node("RUNNING", "COMPLETED")


def test_agent_run_transitions_allowed():
    sm = RunLifecycleStateMachine()
    sm.validate_agent("CREATED", "RUNNING")
    sm.validate_agent("RUNNING", "COMPLETED")


def test_tool_run_transitions_allowed():
    sm = RunLifecycleStateMachine()
    sm.validate_tool("CREATED", "EXECUTING")
    sm.validate_tool("EXECUTING", "SUCCESS")
