from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tools.services.tool_orchestrator import ToolOrchestrator


class _FakeTracer:
    def observe(self, *, as_type, name, input, metadata=None):
        class _Ctx:
            def __enter__(_self):
                return None

            def __exit__(_self, exc_type, exc, tb):
                return False

        return _Ctx()


class TestToolOrchestrator:
    @pytest.mark.asyncio
    async def test_execute_operation_creates_tool_run_and_delegates_execute_tool_run(self):
        tool_run_id = uuid4()
        tool_config_id = uuid4()
        correlation_id = uuid4()
        node_run_id = uuid4()

        repo = MagicMock()
        repo.create_tool_run = AsyncMock(return_value=tool_run_id)

        orchestrator = ToolOrchestrator(
            repository=repo,
            executor=MagicMock(),
            secret_resolver=MagicMock(),
            tracer=_FakeTracer(),
        )
        orchestrator.execute_tool_run = AsyncMock(return_value={"status_code": 200})

        created_tool_run_id, result = await orchestrator.execute_operation(
            tool_config_id=tool_config_id,
            correlation_id=correlation_id,
            node_run_id=node_run_id,
            idempotency_key="key-1",
            input_payload={"x": 1},
        )

        assert created_tool_run_id == tool_run_id
        assert result == {"status_code": 200}
        repo.create_tool_run.assert_awaited_once()
        orchestrator.execute_tool_run.assert_awaited_once_with(tool_run_id=tool_run_id)

    @pytest.mark.asyncio
    async def test_execute_tool_run_success_updates_run_and_creates_artifact(self):
        tool_run_id = uuid4()
        tool_config_id = uuid4()
        correlation_id = uuid4()

        repo = MagicMock()
        repo.get_tool_run = AsyncMock(
            return_value=SimpleNamespace(
                tool_run_id=tool_run_id,
                tool_config_id=tool_config_id,
                input={"x": 1},
                correlation_id=correlation_id,
                node_run_id=None,
                agent_run_id=None,
            )
        )
        repo.get_tool_config = AsyncMock(
            return_value=SimpleNamespace(
                tool_config_id=tool_config_id,
                config={"url": "https://example.com", "method": "POST", "max_attempts": 1},
            )
        )
        repo.update_tool_run_result = AsyncMock()
        repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=uuid4())
        repo.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))
        repo.append_execution_event = AsyncMock()
        repo.create_response_artifact_for_tool_run = AsyncMock(return_value=uuid4())
        repo.create_run_failure_for_tool_run = AsyncMock()

        executor = MagicMock()
        executor.execute_http = AsyncMock(
            return_value={"status_code": 200, "headers": {}, "text": "ok"}
        )

        secret_resolver = MagicMock()
        secret_resolver.resolve = AsyncMock(return_value="secret")
        orchestrator = ToolOrchestrator(
            repository=repo,
            executor=executor,
            secret_resolver=secret_resolver,
            tracer=_FakeTracer(),
        )
        result = await orchestrator.execute_tool_run(tool_run_id=tool_run_id)

        assert result["status_code"] == 200
        repo.update_tool_run_result.assert_called()
        repo.append_execution_event.assert_called()
        repo.create_response_artifact_for_tool_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_run_resolves_secret_refs_and_emits_event(self):
        tool_run_id = uuid4()
        tool_config_id = uuid4()
        correlation_id = uuid4()

        repo = MagicMock()
        repo.get_tool_run = AsyncMock(
            return_value=SimpleNamespace(
                tool_run_id=tool_run_id,
                tool_config_id=tool_config_id,
                input={"x": 1},
                correlation_id=correlation_id,
                node_run_id=None,
                agent_run_id=None,
            )
        )
        repo.get_tool_config = AsyncMock(
            return_value=SimpleNamespace(
                tool_config_id=tool_config_id,
                config={
                    "url": "https://example.com",
                    "method": "POST",
                    "max_attempts": 1,
                    "headers": {"Authorization": {"secret_ref": "env:TEST_SECRET"}},
                },
            )
        )
        repo.update_tool_run_result = AsyncMock()
        repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=uuid4())
        repo.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))
        repo.append_execution_event = AsyncMock()
        repo.create_response_artifact_for_tool_run = AsyncMock(return_value=uuid4())
        repo.create_run_failure_for_tool_run = AsyncMock()

        executor = MagicMock()
        executor.execute_http = AsyncMock(
            return_value={"status_code": 200, "headers": {}, "text": "ok"}
        )

        secret_resolver = MagicMock()
        secret_resolver.resolve = AsyncMock(return_value="secret-value")
        orchestrator = ToolOrchestrator(
            repository=repo,
            executor=executor,
            secret_resolver=secret_resolver,
            tracer=_FakeTracer(),
        )
        await orchestrator.execute_tool_run(tool_run_id=tool_run_id)

        secret_resolver.resolve.assert_called_once()
        assert any(
            str(call.kwargs.get("event_type")) == "SecretAccessed"
            for call in repo.append_execution_event.mock_calls
        )
