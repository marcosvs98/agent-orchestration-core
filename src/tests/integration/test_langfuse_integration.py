from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from domain.execution.services.execution_service import ExecutionService
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.governance.services.execution_limit_service import ExecutionLimitService
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer


@pytest.fixture
def mock_langfuse_client():
    with patch("langfuse.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_observation = MagicMock()
        mock_observation.update = MagicMock()
        
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_span.update = MagicMock()
        
        mock_generation = MagicMock()
        mock_generation.__enter__ = MagicMock(return_value=mock_generation)
        mock_generation.__exit__ = MagicMock(return_value=False)
        mock_generation.update = MagicMock()
        
        mock_client.start_as_current_observation = MagicMock(
            side_effect=lambda **kwargs: mock_span if kwargs.get("as_type") == "span" else mock_generation
        )
        mock_client.get_current_observation_id = MagicMock(return_value="obs_123")
        mock_client.create_trace_id = MagicMock(return_value=str(uuid4()))
        mock_client.flush = MagicMock()
        mock_client.shutdown = MagicMock()
        
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def execution_service(mock_langfuse_client):
    mock_repo = AsyncMock(spec=ExecutionRepository)
    mock_idempotency = AsyncMock(spec=IdempotencyService)
    mock_lifecycle = MagicMock(spec=RunLifecycleStateMachine)
    mock_limits = MagicMock(spec=ExecutionLimitService)
    
    service = ExecutionService(
        repository=mock_repo,
        idempotency=mock_idempotency,
        lifecycle=mock_lifecycle,
        limits=mock_limits,
    )
    service.llm_executor = MagicMock()
    return service


@pytest.mark.asyncio
async def test_tracer_integration_with_execution_service(execution_service, mock_langfuse_client):
    assert execution_service.tracer is not None
    assert isinstance(execution_service.tracer, LangfuseRuntimeTracer)
    
    flow_run_id = uuid4()
    trace_context = execution_service.tracer.start_flow_trace(
        flow_run_id=flow_run_id,
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        tenant_id=uuid4(),
        session_id=None,
        user_id=None,
    )
    
    assert trace_context.trace_id is not None
    assert trace_context.flow_run_id == flow_run_id
    
    execution_service.tracer.flush()
    mock_langfuse_client.flush.assert_called_once()
    
    execution_service.tracer.shutdown()
    mock_langfuse_client.shutdown.assert_called_once()
