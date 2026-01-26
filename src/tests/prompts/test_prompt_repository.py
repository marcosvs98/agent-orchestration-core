from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType


class TestPromptRepository:
    @pytest.mark.asyncio
    async def test_get_active_prompt_returns_none_when_not_found(self):
        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        db.get_session = MagicMock(return_value=session.__aenter__())
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        repo = PromptRepository(db)
        result = await repo.get_active_prompt(NodeType.IntentToolSelectionNode.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_prompt_returns_prompt_when_found(self):
        from infra.database.models.prompts.node_prompt import NodePrompt as NodePromptModel

        prompt_id = uuid4()
        model = NodePromptModel(
            prompt_id=prompt_id,
            node_type=NodeType.IntentToolSelectionNode.value,
            template_text="Test prompt",
            input_schema_id=None,
            output_schema_id=None,
            version=1,
            frozen_hash="abc123",
            is_active=True,
            description=None,
            created_by="test_user",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        db.get_session = MagicMock(return_value=session.__aenter__())
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=model)))

        repo = PromptRepository(db)
        result = await repo.get_active_prompt(NodeType.IntentToolSelectionNode.value)

        assert result is not None
        assert result.prompt_id == prompt_id
        assert result.node_type == NodeType.IntentToolSelectionNode.value
        assert result.template_text == "Test prompt"
        assert result.version == 1
        assert result.frozen_hash == "abc123"

    @pytest.mark.asyncio
    async def test_create_prompt_creates_new_prompt(self):
        from infra.database.models.prompts.node_prompt import NodePrompt as NodePromptModel

        prompt_id = uuid4()
        create = NodePromptCreate(
            node_type=NodeType.IntentToolSelectionNode.value,
            template_text="New prompt",
            description="Test description",
            created_by="test_user",
        )

        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        db.get_session = MagicMock(return_value=session.__aenter__())
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        model = NodePromptModel(
            prompt_id=prompt_id,
            node_type=create.node_type,
            template_text=create.template_text,
            input_schema_id=create.input_schema_id,
            output_schema_id=create.output_schema_id,
            version=1,
            frozen_hash="hash123",
            is_active=True,
            description=create.description,
            created_by=create.created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.refresh = MagicMock(side_effect=lambda m: setattr(m, 'prompt_id', prompt_id))

        repo = PromptRepository(db)
        result = await repo.create_prompt(create, "hash123")

        assert result is not None
        assert result.node_type == create.node_type
        assert result.template_text == create.template_text
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_deactivate_prompt_sets_is_active_false(self):
        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        db.get_session = MagicMock(return_value=session.__aenter__())
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        repo = PromptRepository(db)
        await repo.deactivate_prompt(uuid4())

        session.execute.assert_called_once()
        session.commit.assert_called_once()
