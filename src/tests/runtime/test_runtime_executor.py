import contextlib
import uuid

import pytest

from domain.execution.services.graph_runtime.executor import RuntimeExecutor
from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan, CompiledEdge
from domain.execution.services.graph_runtime.nodes import IntentToolSelectionNode
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import ExecutionContext, NodeResult
from domain.execution.schemas.execution import FlowRunInput
from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge, FlowGraphNodeSpec
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler


class _FakeRepository:
    def __init__(self) -> None:
        self.events = []
        self.node_runs = []
        self.graph_states = []
        self.flow_run_statuses = []
        self.flow_run_outputs = []
        self.flow_run_interaction_results = []

    async def create_node_run(
        self,
        *,
        flow_run_id,
        node_id,
        correlation_id,
        input_payload,
        output_payload,
        status,
        canonical_status,
    ):
        node_run_id = uuid.uuid4()
        self.node_runs.append(
            {
                "flow_run_id": flow_run_id,
                "node_id": node_id,
                "correlation_id": correlation_id,
                "input_payload": input_payload,
                "output_payload": output_payload,
                "status": status,
                "canonical_status": canonical_status,
            }
        )
        return node_run_id

    async def append_execution_event(
        self,
        *,
        tenant_id,
        session_id,
        flow_run_id,
        event_type,
        payload,
        correlation_id,
        causation_id,
        schema_version,
        node_id=None,
        edge_id=None,
    ):
        self.events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "flow_run_id": flow_run_id,
            }
        )

    async def upsert_graph_state(self, *, flow_run_id, state, last_node_run_id):
        self.graph_states.append(
            {"flow_run_id": flow_run_id, "state": state, "last_node_run_id": last_node_run_id}
        )

    async def set_flow_run_status(self, *, flow_run_id, status, canonical_status):
        self.flow_run_statuses.append(
            {
                "flow_run_id": flow_run_id,
                "status": status,
                "canonical_status": canonical_status,
            }
        )

    async def set_flow_run_output(self, *, flow_run_id, output):
        self.flow_run_outputs.append({"flow_run_id": flow_run_id, "output": output})

    async def set_current_interaction_result_for_flow_run(
        self, *, flow_run_id, output, result_node_run_id
    ):
        self.flow_run_interaction_results.append(
            {
                "flow_run_id": flow_run_id,
                "output": output,
                "result_node_run_id": result_node_run_id,
            }
        )


class _FakeTracer:
    def observe(self, *, as_type, name, input, metadata=None):
        return contextlib.nullcontext()


_compiler = FlowGraphCompiler()
_plan_compiler = GraphCompiler()


def _compile_plan(definition: FlowGraphDefinition):
    snapshot, graph_hash = _compiler.compile(definition)
    return _plan_compiler.compile(snapshot, graph_hash)


def _make_definition():
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    return (
        FlowGraphDefinition(
            start_node=node_a,
            nodes={
                node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
                node_b: FlowGraphNodeSpec(type="ResponseNode"),
            },
            edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
        ),
        node_a,
        node_b,
    )


@pytest.mark.asyncio
async def test_runtime_executor_completes_happy_path():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    definition, node_a, node_b = _make_definition()
    await executor.run(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    event_types = [str(e["event_type"]) for e in repo.events]
    assert "FlowCompleted" in event_types
    assert repo.graph_states[-1]["state"]["current_node_id"] == node_b
    assert repo.node_runs[-1]["output_payload"]["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_multiple_edges():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(type="ResponseNode"),
            node_c: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1"),
            FlowGraphEdge(from_node=node_a, to_node=node_c, condition="1 == 1"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    event_types = [str(e["event_type"]) for e in repo.events]
    assert "FlowFailed" in event_types
    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert "multiple_matching_edges" in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_edge_evaluation_error():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    snapshot = {
        "start_node": node_a,
        "nodes": {
            node_a: {"type": "IntentToolSelectionNode", "config": None},
            node_b: {"type": "ResponseNode", "config": None},
        },
        "edges": [
            {
                "from_node": node_a,
                "to_node": node_b,
                "condition": "foo(",
                "compiled_condition": {"type": "unknown"},
            }
        ],
    }
    plan = _plan_compiler.compile(snapshot, "bad-hash")
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=plan,
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert any("edge_evaluation_error" in r for r in reasons)


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_no_matching_edge():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 0")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert "no_matching_edge" in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_node_not_found():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    plan = ExecutionPlan(
        start_node_id="missing",
        ordered_nodes=[],
        adjacency_map={},
        terminal_nodes=set(),
        structural_hash="x",
        nodes={},
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=plan,
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert "node_not_found" in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_unknown_node_type():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="UnknownNodeType"),
            node_b: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert "unknown_node_type" in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_max_steps_exceeded():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    executor.loop_limit = 1000
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    edge_ab = CompiledEdge(
        from_node=node_a,
        to_node=node_b,
        edge_kind="LOOP",
        compiled_condition={"type": "constant", "value": True},
        order=0,
    )
    edge_ba = CompiledEdge(
        from_node=node_b,
        to_node=node_a,
        edge_kind="LOOP",
        compiled_condition={"type": "constant", "value": True},
        order=1,
    )
    plan = ExecutionPlan(
        start_node_id=node_a,
        ordered_nodes=[node_a, node_b],
        adjacency_map={node_a: [edge_ab], node_b: [edge_ba]},
        terminal_nodes=set(),
        structural_hash="x",
        nodes={
            node_a: {"type": "IntentToolSelectionNode", "config": None},
            node_b: {"type": "IntentToolSelectionNode", "config": None},
        },
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=plan,
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert any("max_steps_exceeded" in r or "loop_iteration_limit_exceeded" in r for r in reasons)


@pytest.mark.asyncio
async def test_runtime_executor_completes_with_fallback_node():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(type="FallbackNode"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    event_types = [str(e["event_type"]) for e in repo.events]
    assert "FlowCompleted" in event_types
    assert repo.node_runs[-1]["output_payload"]["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_runtime_executor_persists_state_and_memory():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(
                type="IntentToolSelectionNode",
                config={"output": {"validation_status": "VALID", "confidence": 0.9}},
            ),
            node_b: FlowGraphNodeSpec(type="ToolExecutionNode"),
            node_c: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="validation_status == 'VALID' && confidence >= 0.85"),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="execution_status == 'SUCCESS'"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    assert len(repo.node_runs) == 3
    assert len(repo.graph_states) == 3
    assert repo.graph_states[-1]["state"]["current_node_id"] == node_c


@pytest.mark.asyncio
async def test_runtime_executor_handles_tool_execution_error():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(
                type="ToolExecutionNode",
                config={"output": {"execution_status": "ERROR"}},
            ),
            node_c: FlowGraphNodeSpec(type="FallbackNode"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1"),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="execution_status == 'ERROR'"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    event_types = [str(e["event_type"]) for e in repo.events]
    assert "FlowCompleted" in event_types
    assert repo.node_runs[1]["output_payload"]["status"] == "ERROR"
    assert repo.node_runs[1]["status"] == "FAILED"


@pytest.mark.asyncio
async def test_runtime_executor_handles_clarification_node():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(
                type="ClarificationNode", config={"resume_to_node_id": node_a}
            ),
            node_c: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="validation_status == 'MISSING_FIELDS'"),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="1 == 1"),
        ],
    )
    definition.nodes[node_a].config = {"output": {"validation_status": "MISSING_FIELDS", "confidence": 0.5}}
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    assert repo.node_runs[1]["output_payload"]["status"] == "NEEDS_INPUT"
    assert repo.node_runs[1]["status"] == "PENDING"
    assert repo.flow_run_statuses[-1]["status"] == "WAITING_INPUT"
    assert repo.flow_run_statuses[-1]["canonical_status"] == "WAITING"
    assert repo.graph_states[-1]["state"]["resume_to_node_id"] == node_a


@pytest.mark.asyncio
async def test_runtime_executor_handles_next_state_and_memory_append():
    class CustomNode(IntentToolSelectionNode):
        async def execute(self, context: ExecutionContext, config=None):
            return NodeResult(
                status="SUCCESS",
                payload={"test": "value"},
                next_state={"custom": "state"},
                memory_append={"memory": "entry"},
            )

    repo = _FakeRepository()
    registry = NodeRegistry()
    registry._registry["IntentToolSelectionNode"] = CustomNode
    executor = RuntimeExecutor(repo, _FakeTracer(), registry)
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )

    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    assert repo.graph_states[0]["state"]["state"]["custom"] == "state"
    assert repo.graph_states[0]["state"]["memory"][0]["memory"] == "entry"


@pytest.mark.asyncio
async def test_runtime_executor_emits_edge_evaluated_and_node_started():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="IntentToolSelectionNode"),
            node_b: FlowGraphNodeSpec(type="ResponseNode"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=_compile_plan(definition),
    )

    event_types = [e["event_type"] for e in repo.events]
    assert "EdgeEvaluated" in event_types
    assert "NodeStarted" in event_types


@pytest.mark.asyncio
async def test_runtime_executor_enforces_loop_limit():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer())
    executor.loop_limit = 2
    node_a = str(uuid.uuid4())
    edge_loop = CompiledEdge(
        from_node=node_a,
        to_node=node_a,
        edge_kind="LOOP",
        compiled_condition={"type": "constant", "value": True},
        order=0,
    )
    plan = ExecutionPlan(
        start_node_id=node_a,
        ordered_nodes=[node_a],
        adjacency_map={node_a: [edge_loop]},
        terminal_nodes=set(),
        structural_hash="x",
        nodes={node_a: {"type": "IntentToolSelectionNode", "config": None}},
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        input_payload=FlowRunInput(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        plan=plan,
    )

    reasons = [e["payload"]["reason"] for e in repo.events if "reason" in e["payload"]]
    assert any("loop_iteration_limit_exceeded" in r for r in reasons)
