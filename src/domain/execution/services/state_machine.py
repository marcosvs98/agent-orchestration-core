from enum import StrEnum

from exceptions.service_exceptions import InvalidTransitionException


class RunStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_INPUT = "WAITING_INPUT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    RunStatus.CREATED: {RunStatus.QUEUED, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.RUNNING: {RunStatus.WAITING_INPUT, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.WAITING_INPUT: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


class ExecutionStateMachine:
    def validate_transition(self, current: str, target: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(str(current), set())
        if target not in allowed:
            raise InvalidTransitionException(
                message=f"Invalid transition: {current} -> {target}"
            )


# Planning (10) canonical statuses (dual-layer)
class FlowRunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class NodeRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SKIPPED = "SKIPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ToolRunStatus(StrEnum):
    CREATED = "CREATED"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class RunLifecycleStateMachine:
    """Canonical lifecycle (Planning 10) with closed transitions per run type."""

    flow_transitions: dict[FlowRunStatus, set[FlowRunStatus]] = {
        FlowRunStatus.CREATED: {FlowRunStatus.RUNNING, FlowRunStatus.FAILED},
        FlowRunStatus.RUNNING: {
            FlowRunStatus.WAITING,
            FlowRunStatus.COMPLETED,
            FlowRunStatus.FAILED,
            FlowRunStatus.ESCALATED,
        },
        FlowRunStatus.WAITING: {
            FlowRunStatus.RUNNING,
            FlowRunStatus.FAILED,
            FlowRunStatus.ESCALATED,
        },
        FlowRunStatus.ESCALATED: set(),
        FlowRunStatus.COMPLETED: set(),
        FlowRunStatus.FAILED: set(),
    }

    node_transitions: dict[NodeRunStatus, set[NodeRunStatus]] = {
        NodeRunStatus.PENDING: {NodeRunStatus.RUNNING, NodeRunStatus.SKIPPED},
        NodeRunStatus.RUNNING: {NodeRunStatus.COMPLETED, NodeRunStatus.FAILED},
        NodeRunStatus.SKIPPED: set(),
        NodeRunStatus.COMPLETED: set(),
        NodeRunStatus.FAILED: set(),
    }

    agent_transitions: dict[AgentRunStatus, set[AgentRunStatus]] = {
        AgentRunStatus.CREATED: {AgentRunStatus.RUNNING, AgentRunStatus.FAILED},
        AgentRunStatus.RUNNING: {AgentRunStatus.COMPLETED, AgentRunStatus.FAILED},
        AgentRunStatus.COMPLETED: set(),
        AgentRunStatus.FAILED: set(),
    }

    tool_transitions: dict[ToolRunStatus, set[ToolRunStatus]] = {
        ToolRunStatus.CREATED: {
            ToolRunStatus.EXECUTING,
            ToolRunStatus.ERROR,
            ToolRunStatus.TIMEOUT,
        },
        ToolRunStatus.EXECUTING: {
            ToolRunStatus.SUCCESS,
            ToolRunStatus.ERROR,
            ToolRunStatus.TIMEOUT,
        },
        ToolRunStatus.SUCCESS: set(),
        ToolRunStatus.ERROR: set(),
        ToolRunStatus.TIMEOUT: set(),
    }

    def validate_flow(self, current: FlowRunStatus, target: FlowRunStatus) -> None:
        if target not in self.flow_transitions.get(current, set()):
            raise InvalidTransitionException(
                message=f"Invalid FlowRun transition: {current} -> {target}"
            )

    def validate_node(self, current: NodeRunStatus, target: NodeRunStatus) -> None:
        if target not in self.node_transitions.get(current, set()):
            raise InvalidTransitionException(
                message=f"Invalid NodeRun transition: {current} -> {target}"
            )

    def validate_agent(self, current: AgentRunStatus, target: AgentRunStatus) -> None:
        if target not in self.agent_transitions.get(current, set()):
            raise InvalidTransitionException(
                message=f"Invalid AgentRun transition: {current} -> {target}"
            )

    def validate_tool(self, current: ToolRunStatus, target: ToolRunStatus) -> None:
        if target not in self.tool_transitions.get(current, set()):
            raise InvalidTransitionException(
                message=f"Invalid ToolRun transition: {current} -> {target}"
            )
