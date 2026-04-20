import pytest
from uuid import uuid4

from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)


@pytest.fixture
def mock_agents_repository():
    class MockAgentsRepository:
        def __init__(self):
            self.get_agent_version_id_by_node_id_calls = []
            self.get_agent_version_calls = []
            self._binding = {}
            self._versions = {}

        async def get_agent_version_id_by_node_id(self, node_id):
            self.get_agent_version_id_by_node_id_calls.append(node_id)
            return self._binding.get(node_id)

        async def get_agent_version(self, agent_version_id):
            self.get_agent_version_calls.append(agent_version_id)
            return self._versions.get(agent_version_id)

    return MockAgentsRepository()


@pytest.mark.asyncio
async def test_resolve_system_prompt_cache_miss_stores_and_returns(mock_agents_repository):
    flow_run_id = uuid4()
    node_id = uuid4()
    agent_version_id = uuid4()
    state = {}

    class FakeVersion:
        system_prompt = "You are a helper."

    mock_agents_repository._binding[node_id] = agent_version_id
    mock_agents_repository._versions[agent_version_id] = FakeVersion()

    resolver = AgentRuntimeResolver(mock_agents_repository)
    result = await resolver.resolve_system_prompt(flow_run_id, node_id, state)

    assert result == "You are a helper."
    assert state[f"_agent_system_prompt_{node_id}"] == "You are a helper."
    assert len(mock_agents_repository.get_agent_version_id_by_node_id_calls) == 1
    assert len(mock_agents_repository.get_agent_version_calls) == 1


@pytest.mark.asyncio
async def test_resolve_system_prompt_cache_hit_does_not_call_repository(mock_agents_repository):
    flow_run_id = uuid4()
    node_id = uuid4()
    state = {f"_agent_system_prompt_{node_id}": "cached"}

    resolver = AgentRuntimeResolver(mock_agents_repository)
    result = await resolver.resolve_system_prompt(flow_run_id, node_id, state)

    assert result == "cached"
    assert len(mock_agents_repository.get_agent_version_id_by_node_id_calls) == 0
    assert len(mock_agents_repository.get_agent_version_calls) == 0


@pytest.mark.asyncio
async def test_resolve_system_prompt_missing_binding_returns_none(mock_agents_repository):
    flow_run_id = uuid4()
    node_id = uuid4()
    state = {}

    resolver = AgentRuntimeResolver(mock_agents_repository)
    result = await resolver.resolve_system_prompt(flow_run_id, node_id, state)

    assert result is None
    assert state[f"_agent_system_prompt_{node_id}"] is None
    assert len(mock_agents_repository.get_agent_version_id_by_node_id_calls) == 1
    assert len(mock_agents_repository.get_agent_version_calls) == 0


@pytest.mark.asyncio
async def test_resolve_system_prompt_empty_system_prompt_returns_none(mock_agents_repository):
    flow_run_id = uuid4()
    node_id = uuid4()
    agent_version_id = uuid4()
    state = {}

    class FakeVersion:
        system_prompt = None

    mock_agents_repository._binding[node_id] = agent_version_id
    mock_agents_repository._versions[agent_version_id] = FakeVersion()

    resolver = AgentRuntimeResolver(mock_agents_repository)
    result = await resolver.resolve_system_prompt(flow_run_id, node_id, state)

    assert result is None
    assert state[f"_agent_system_prompt_{node_id}"] is None
