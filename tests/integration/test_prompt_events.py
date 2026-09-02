from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType
from domain.prompts.services.prompt_service import PromptService


class TestPromptEvents:
    @pytest.mark.asyncio
    async def test_create_prompt_emits_node_prompt_updated_event(self):
        prompt_id = uuid4()
        tenant_id = uuid4()

        create = NodePromptCreate(
            node_type=NodeType.ToolResolver.value,
            template_text="Test prompt",
            description="Test",
            created_by="test_user",
        )

        created_prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=create.node_type,
            template_text=create.template_text,
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash=PromptService._calculate_frozen_hash(create.template_text),
            is_active=True,
            description=create.description,
            created_by=create.created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        repo.get_active_prompt = AsyncMock(return_value=None)
        repo.create_prompt = AsyncMock(return_value=created_prompt)

        exec_repo = MagicMock(spec=ExecutionRepository)
        exec_repo.append_execution_event = AsyncMock()

        tracer = MagicMock()
        tracer.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())

        service = PromptService(tracer=tracer, repository=repo, execution_repository=exec_repo)
        await service.create_or_update_prompt(create, tenant_id=tenant_id)

        exec_repo.append_execution_event.assert_called_once()
        call_args = exec_repo.append_execution_event.call_args
        assert call_args.kwargs["event_type"] == ExecutionEventType.NodePromptUpdated
        assert call_args.kwargs["tenant_id"] == tenant_id
        payload = call_args.kwargs["payload"]
        assert payload["prompt_id"] == str(prompt_id)
        assert payload["node_type"] == NodeType.ToolResolver.value
        assert payload["version"] == 1
        assert payload["frozen_hash"] == created_prompt.frozen_hash
