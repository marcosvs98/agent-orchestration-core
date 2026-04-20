from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException


def _fake_tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


class TestPromptService:
    @pytest.mark.asyncio
    async def test_get_prompt_returns_from_cache_when_available(self):
        from domain.prompts.services.prompt_service import PromptCacheEntry

        prompt_id = uuid4()
        prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=NodeType.ToolResolver.value,
            template_text="Cached prompt",
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash="hash123",
            is_active=True,
            description=None,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        service = PromptService(tracer=_fake_tracer(), repository=repo)

        import time
        cache_entry = PromptCacheEntry(prompt=prompt, timestamp=time.time(), ttl=3600)
        service._cache[NodeType.ToolResolver.value] = cache_entry

        result = await service.get_prompt(NodeType.ToolResolver.value)

        assert result is not None
        assert result.prompt_id == prompt_id

    @pytest.mark.asyncio
    async def test_get_prompt_fetches_from_repository_when_cache_miss(self):
        prompt_id = uuid4()
        prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=NodeType.ToolResolver.value,
            template_text="Repository prompt",
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash="hash123",
            is_active=True,
            description=None,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        repo.get_active_prompt = AsyncMock(return_value=prompt)
        service = PromptService(tracer=_fake_tracer(), repository=repo)

        result = await service.get_prompt(NodeType.ToolResolver.value)

        assert result is not None
        assert result.prompt_id == prompt_id
        repo.get_active_prompt.assert_called_once_with(NodeType.ToolResolver.value)

    @pytest.mark.asyncio
    async def test_create_or_update_prompt_creates_new_prompt(self):
        prompt_id = uuid4()
        create = NodePromptCreate(
            node_type=NodeType.ToolResolver.value,
            template_text="New prompt text",
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

        service = PromptService(
            tracer=_fake_tracer(), repository=repo, execution_repository=exec_repo
        )
        result = await service.create_or_update_prompt(create, tenant_id=uuid4())

        assert result is not None
        assert result.prompt_id == prompt_id
        assert result.version == 1
        repo.create_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_or_update_prompt_updates_existing_prompt(self):
        existing_id = uuid4()
        existing = NodePrompt(
            prompt_id=existing_id,
            node_type=NodeType.ToolResolver.value,
            template_text="Old prompt",
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash="old_hash",
            is_active=True,
            description=None,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        create = NodePromptCreate(
            node_type=NodeType.ToolResolver.value,
            template_text="Updated prompt text",
            description="Updated",
            created_by="test_user",
        )

        updated_prompt = NodePrompt(
            prompt_id=uuid4(),
            node_type=create.node_type,
            template_text=create.template_text,
            input_schema=None,
            output_schema=None,
            version=2,
            frozen_hash=PromptService._calculate_frozen_hash(create.template_text),
            is_active=True,
            description=create.description,
            created_by=create.created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        repo.get_active_prompt = AsyncMock(return_value=existing)
        repo.update_prompt = AsyncMock(return_value=updated_prompt)
        exec_repo = MagicMock(spec=ExecutionRepository)
        exec_repo.append_execution_event = AsyncMock()

        service = PromptService(
            tracer=_fake_tracer(), repository=repo, execution_repository=exec_repo
        )
        result = await service.create_or_update_prompt(create, tenant_id=uuid4())

        assert result is not None
        assert result.version == 2
        repo.update_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_prompt_deactivates_and_invalidates_cache(self):
        from domain.prompts.services.prompt_service import PromptCacheEntry

        prompt_id = uuid4()
        prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=NodeType.ToolResolver.value,
            template_text="Prompt to deactivate",
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash="hash123",
            is_active=True,
            description=None,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        repo.get_active_prompt = AsyncMock(return_value=prompt)
        repo.deactivate_prompt = AsyncMock()
        service = PromptService(tracer=_fake_tracer(), repository=repo)

        import time
        cache_entry = PromptCacheEntry(prompt=prompt, timestamp=time.time(), ttl=3600)
        service._cache[NodeType.ToolResolver.value] = cache_entry

        await service.deactivate_prompt(NodeType.ToolResolver.value)

        repo.deactivate_prompt.assert_called_once_with(prompt_id)
        assert NodeType.ToolResolver.value not in service._cache

    def test_calculate_frozen_hash_returns_consistent_hash(self):
        text = "Test prompt text"
        hash1 = PromptService._calculate_frozen_hash(text)
        hash2 = PromptService._calculate_frozen_hash(text)

        assert hash1 == hash2
        assert len(hash1) == 64
        assert isinstance(hash1, str)
