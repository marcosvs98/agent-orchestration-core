import contextlib
import uuid
from types import SimpleNamespace

import pytest

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.executor import RuntimeExecutor
from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan, CompiledEdge
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.execution.schemas.execution import FlowFailureReason, FlowRunInput
from domain.prompts.schemas.prompt import NodeType
from domain.flows.schemas.graph import EdgeKind, FlowGraphDefinition, FlowGraphEdge, FlowGraphNodeSpec
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler


class _FakeRepository:
    def __init__(self) -> None:
        self.events = []
        self.node_runs = []
        self.graph_states = []
        self.flow_run_statuses = []
        self.flow_run_outputs = []
        self.flow_run_interaction_results = []
        self.flow_run_failures = []
        self.flow_run_completions = []

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
                "node_run_id": node_run_id,
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

    async def update_node_run_result(
        self,
        *,
        node_run_id,
        output_payload,
        status,
        canonical_status,
    ):
        for run in self.node_runs:
            if run["node_run_id"] == node_run_id:
                run["output_payload"] = output_payload
                run["status"] = status
                run["canonical_status"] = canonical_status
                return

    async def fail_flow_run(self, *, flow_run_id, failure_reason, error=None):
        self.flow_run_failures.append(
            {
                "flow_run_id": flow_run_id,
                "failure_reason": failure_reason,
                "error": error,
            }
        )

    async def complete_flow_run(self, *, flow_run_id, status, output):
        self.flow_run_completions.append(
            {"flow_run_id": flow_run_id, "status": status, "output": output}
        )

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


def _stub_registry() -> NodeRegistry:
    return _StubRuntimeRegistry(_FakeTracer())


class _StubRuntimeRegistry(NodeRegistry):
    def resolve(self, node_type: str):
        if node_type == NodeType.ToolResolver.value:

            class _StubToolResolver:
                node_type = NodeType.ToolResolver
                side_effect = False
                deterministic = True

                def __init__(self) -> None:
                    pass

                async def execute(self, context: ExecutionContext, config=None):
                    cfg = config or {}
                    merged = {"result": [], "validation_status": "VALID", "confidence": 1.0}
                    merged.update(cfg.get("output") or {})
                    ns = {**(context.state or {}), NodeType.ToolResolver.value: merged}
                    return NodeResult(
                        node=NodeType.ToolResolver,
                        status=NodeExecutionStatus.SUCCESS,
                        data=merged,
                        next_state=ns,
                    )

            return _StubToolResolver

        if node_type == NodeType.ResponseBuilder.value:

            class _StubResponseBuilder:
                node_type = NodeType.ResponseBuilder
                side_effect = False
                deterministic = True

                def __init__(self) -> None:
                    pass

                async def execute(self, context: ExecutionContext, config=None):
                    data = {"text": "ok"}
                    ns = {**(context.state or {}), NodeType.ResponseBuilder.value: data}
                    return NodeResult(
                        node=NodeType.ResponseBuilder,
                        status=NodeExecutionStatus.SUCCESS,
                        data=data,
                        next_state=ns,
                    )

            return _StubResponseBuilder

        if node_type == NodeType.HumanFallback.value:

            class _StubHumanFallback:
                node_type = NodeType.HumanFallback
                side_effect = False
                deterministic = True

                def __init__(self) -> None:
                    pass

                async def execute(self, context: ExecutionContext, config=None):
                    data = {"fallback": True}
                    ns = {**(context.state or {}), NodeType.HumanFallback.value: data}
                    return NodeResult(
                        node=NodeType.HumanFallback,
                        status=NodeExecutionStatus.SUCCESS,
                        data=data,
                        next_state=ns,
                    )

            return _StubHumanFallback

        if node_type == NodeType.ToolExecutor.value:

            class _StubToolExecutor:
                node_type = NodeType.ToolExecutor
                side_effect = False
                deterministic = True

                def __init__(self) -> None:
                    pass

                async def execute(self, context: ExecutionContext, config=None):
                    cfg = config or {}
                    merged = {"execution_status": "SUCCESS", "result": []}
                    merged.update(cfg.get("output") or {})
                    ok = merged.get("execution_status") != "ERROR"
                    st = (
                        NodeExecutionStatus.SUCCESS if ok else NodeExecutionStatus.ERROR
                    )
                    ns = {**(context.state or {}), NodeType.ToolExecutor.value: merged}
                    return NodeResult(
                        node=NodeType.ToolExecutor,
                        status=st,
                        data=merged,
                        next_state=ns,
                    )

            return _StubToolExecutor

        if node_type == NodeType.QueryClarifier.value:

            class _StubQueryClarifier:
                node_type = NodeType.QueryClarifier
                side_effect = False
                deterministic = True

                def __init__(self) -> None:
                    pass

                async def execute(self, context: ExecutionContext, config=None):
                    data = {"clarify": True}
                    ns = {**(context.state or {}), NodeType.QueryClarifier.value: data}
                    return NodeResult(
                        node=NodeType.QueryClarifier,
                        status=NodeExecutionStatus.NEEDS_INPUT,
                        data=data,
                        next_state=ns,
                    )

            return _StubQueryClarifier

        return super().resolve(node_type)


_compiler = FlowGraphCompiler()
_plan_compiler = GraphCompiler(_FakeTracer())


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
                node_a: FlowGraphNodeSpec(type="ToolResolver"),
                node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
            },
            edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
        ),
        node_a,
        node_b,
    )


@pytest.mark.asyncio
async def test_runtime_executor_completes_happy_path():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    definition, node_a, node_b = _make_definition()
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
            node_c: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1"),
            FlowGraphEdge(from_node=node_a, to_node=node_c, condition="1 == 1"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.MULTIPLE_MATCHING_EDGES in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_edge_evaluation_error():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    snapshot = {
        "start_node": node_a,
        "nodes": {
            node_a: {"type": "ToolResolver", "config": None},
            node_b: {"type": "ResponseBuilder", "config": None},
        },
        "edges": [
            {
                "from_node": node_a,
                "to_node": node_b,
                "condition": "foo(",
                "compiled_condition": [{"invalid": True}],
            }
        ],
    }
    plan = _plan_compiler.compile(snapshot, "bad-hash")
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.EDGE_EVALUATION_ERROR in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_no_matching_edge():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 0")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.NO_MATCHING_EDGE in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_node_not_found():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
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
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.NODE_NOT_FOUND in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_unknown_node_type():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="UnknownNodeType"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.UNKNOWN_NODE_TYPE in reasons


@pytest.mark.asyncio
async def test_runtime_executor_fails_on_max_steps_exceeded():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    executor.loop_limit = 1000
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    always_true = EdgeEvaluator.compile_condition("1 == 1")
    edge_ab = CompiledEdge(
        from_node=node_a,
        to_node=node_b,
        edge_kind=EdgeKind.LOOP,
        compiled_condition=always_true,
        order=0,
    )
    edge_ba = CompiledEdge(
        from_node=node_b,
        to_node=node_a,
        edge_kind=EdgeKind.LOOP,
        compiled_condition=always_true,
        order=1,
    )
    plan = ExecutionPlan(
        start_node_id=node_a,
        ordered_nodes=[node_a, node_b],
        adjacency_map={node_a: [edge_ab], node_b: [edge_ba]},
        terminal_nodes=set(),
        structural_hash="x",
        nodes={
            node_a: {"type": "ToolResolver", "config": None},
            node_b: {"type": "ToolResolver", "config": None},
        },
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert (
        FlowFailureReason.MAX_STEPS_EXCEEDED in reasons
        or FlowFailureReason.EDGE_EVALUATION_ERROR in reasons
    )


@pytest.mark.asyncio
async def test_runtime_executor_completes_with_fallback_node():
    repo = _FakeRepository()
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="HumanFallback"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(
                type="ToolResolver",
                config={"output": {"validation_status": "VALID", "confidence": 0.9}},
            ),
            node_b: FlowGraphNodeSpec(type="ToolExecutor"),
            node_c: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[
            FlowGraphEdge(
                from_node=node_a,
                to_node=node_b,
                condition="validation_status == 'VALID' and confidence >= 0.85",
            ),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="execution_status == 'SUCCESS'"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(
                type="ToolExecutor",
                config={"output": {"execution_status": "ERROR"}},
            ),
            node_c: FlowGraphNodeSpec(type="HumanFallback"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1"),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="execution_status == 'ERROR'"),
        ],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(
                type="QueryClarifier", config={"resume_to_node_id": node_a}
            ),
            node_c: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[
            FlowGraphEdge(from_node=node_a, to_node=node_b, condition="validation_status == 'MISSING_FIELDS'"),
            FlowGraphEdge(from_node=node_b, to_node=node_c, condition="1 == 1"),
        ],
    )
    definition.nodes[node_a].config = {"output": {"validation_status": "MISSING_FIELDS", "confidence": 0.5}}
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
async def test_runtime_executor_handles_next_state_and_memory_snapshot():
    class CustomNode:
        node_type = NodeType.ToolResolver
        side_effect = False
        deterministic = True

        def __init__(self) -> None:
            pass

        async def execute(self, context: ExecutionContext, config=None):
            merged = {"result": [], "validation_status": "VALID", "confidence": 1.0}
            ns = {
                **(context.state or {}),
                NodeType.ToolResolver.value: merged,
                "custom": "state",
            }
            return NodeResult(
                node=NodeType.ToolResolver,
                status=NodeExecutionStatus.SUCCESS,
                data=merged,
                next_state=ns,
                memory=[*context.memory, {"memory": "entry"}],
            )

    class _RegistryWithCustomTool(_StubRuntimeRegistry):
        def resolve(self, node_type: str):
            if node_type == NodeType.ToolResolver.value:
                return CustomNode
            return super().resolve(node_type)

    repo = _FakeRepository()
    executor = RuntimeExecutor(
        repo, _FakeTracer(), registry=_RegistryWithCustomTool(_FakeTracer())
    )
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )

    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    definition = FlowGraphDefinition(
        start_node=node_a,
        nodes={
            node_a: FlowGraphNodeSpec(type="ToolResolver"),
            node_b: FlowGraphNodeSpec(type="ResponseBuilder"),
        },
        edges=[FlowGraphEdge(from_node=node_a, to_node=node_b, condition="1 == 1")],
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    executor = RuntimeExecutor(repo, _FakeTracer(), registry=_stub_registry())
    executor.loop_limit = 2
    node_a = str(uuid.uuid4())
    edge_loop = CompiledEdge(
        from_node=node_a,
        to_node=node_a,
        edge_kind=EdgeKind.LOOP,
        compiled_condition=EdgeEvaluator.compile_condition("1 == 1"),
        order=0,
    )
    plan = ExecutionPlan(
        start_node_id=node_a,
        ordered_nodes=[node_a],
        adjacency_map={node_a: [edge_loop]},
        terminal_nodes=set(),
        structural_hash="x",
        nodes={node_a: {"type": "ToolResolver", "config": None}},
    )
    await executor.run(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        trace_context=SimpleNamespace(user_id="test-user"),
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
    assert FlowFailureReason.EDGE_EVALUATION_ERROR in reasons
