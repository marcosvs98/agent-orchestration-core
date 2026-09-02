from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment

from adapters.temporal.dtos import FlowRunWorkflowInput


@pytest_asyncio.fixture(scope="module")
async def workflow_env() -> AsyncIterator[WorkflowEnvironment]:
    env = await WorkflowEnvironment.start_local(data_converter=pydantic_data_converter)
    try:
        yield env
    finally:
        await env.shutdown()


@pytest.fixture
def task_queue() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def workflow_input() -> FlowRunWorkflowInput:
    return FlowRunWorkflowInput(
        flow_run_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        user_id="test-user",
        flow_id=str(uuid.uuid4()),
        flow_version_id=str(uuid.uuid4()),
        interaction_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        idempotency_key="test-key",
    )
