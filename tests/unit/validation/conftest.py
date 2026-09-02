"""Shared fakes for the validation slice.

These tests drive `ExecutionService` against a mocked repository. Every repository method the
service uses is awaited except `start_event_batching`, so an `AsyncMock` root with that one
attribute overridden keeps the fakes honest without enumerating the whole surface.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.governance.schemas.runtime_policy import (
    ResolvedRuntimePolicy,
    RuntimePolicyDefinition,
    RuntimePolicyScope,
    RuntimePolicySource,
)


class FakeIdempotency(IdempotencyService):
    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    def build_key(self, tenant_id: UUID, endpoint: str, idempotency_key: str) -> str:  # type: ignore[override]
        return f"{tenant_id}:{endpoint}:{idempotency_key}"

    async def try_acquire(self, key: str) -> bool:  # type: ignore[override]
        return key not in self.store

    async def get(self, key: str) -> dict | None:  # type: ignore[override]
        return self.store.get(key)

    async def set_result(self, key: str, result: dict) -> None:  # type: ignore[override]
        self.store[key] = result


def make_execution_repository(
    *, tenant_id: UUID, flow_id: UUID, flow_version_id: UUID, user_id: str = "test-user"
):
    """Repository double wired for the happy path of `create_flow_run`."""

    repository = AsyncMock()
    repository.start_event_batching = MagicMock()
    repository.end_event_batching = AsyncMock()
    repository.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(
            status="PUBLISHED",
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            to_dict=lambda: {"flow_version_id": str(flow_version_id)},
        )
    )
    repository.get_flow = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id, name="flow"))
    repository.get_active_flow_version_id = AsyncMock(return_value=flow_version_id)
    repository.get_active_flow_deployment = AsyncMock(return_value=None)
    repository.get_flow_snapshot_by_id = AsyncMock(return_value=None)
    repository.get_flow_snapshot_by_flow_version = AsyncMock(return_value=None)
    repository.get_graph_state = AsyncMock(return_value=None)
    repository.get_session = AsyncMock(
        return_value=SimpleNamespace(session_id=uuid4(), tenant_id=tenant_id, user_id=user_id)
    )
    repository.get_latest_waiting_flow_run_id = AsyncMock(return_value=(None, []))
    repository.get_flow_run = AsyncMock(return_value=None)
    repository.create_interaction = AsyncMock(return_value=uuid4())
    repository.create_flow_run = AsyncMock(return_value=uuid4())
    repository.get_active_billing_policy_version_id = AsyncMock(return_value=uuid4())
    repository.get_flow_graph_snapshot_by_flow_version = AsyncMock(
        return_value=SimpleNamespace(
            graph_hash="hash",
            flow_graph_snapshot_id=uuid4(),
            snapshot=minimal_graph_snapshot(),
        )
    )
    return repository


def minimal_graph_snapshot() -> dict[str, object]:
    return {
        "start_node": "a",
        "nodes": {
            "a": {"id": "a", "type": "IntentClassifier"},
            "b": {"id": "b", "type": "ResponseBuilder"},
        },
        "edges": [
            {
                "from_node": "a",
                "to_node": "b",
                "compiled_condition": EdgeEvaluator.compile_condition("1 == 1"),
            }
        ],
    }


def stub_runtime_dependencies(service) -> None:
    """Neutralise collaborators the service builds for itself from a mocked repository."""

    service.llm_executor = MagicMock()
    service.runtime = MagicMock()
    service.runtime.run = AsyncMock()
    service.cache_adapter.get = AsyncMock(return_value=None)
    service.cache_adapter.set = AsyncMock()
    service.hook.on_flow_start = AsyncMock()
    service.tools_service.list_available_tools_for_execution = AsyncMock(return_value=[])
    service._rag_repository.get_rag_config = AsyncMock(return_value=None)
    service.policy_resolver.resolve = AsyncMock(
        return_value=ResolvedRuntimePolicy(
            source=RuntimePolicySource.DEFAULT,
            runtime_policy_id=None,
            version="1",
            definition=RuntimePolicyDefinition.model_validate(
                service.default_policy["policy_definition"]
            ),
            scope=RuntimePolicyScope.TENANT,
            flow_id=None,
        )
    )


@pytest.fixture
def idempotency() -> FakeIdempotency:
    return FakeIdempotency()
