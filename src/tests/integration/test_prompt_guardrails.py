from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from domain.llm.schemas.llm import LLMRequest, LLMTaskType
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodeType
from domain.prompts.services.prompt_service import PromptService


class TestPromptGuardrails:
    @pytest.mark.asyncio
    async def test_prompt_service_validates_prompt_before_persisting(self):
        create = NodePromptCreate(
            node_type=NodeType.IntentToolSelectionNode.value,
            template_text="Valid prompt",
            description="Test",
        )

        created_prompt = NodePrompt(
            prompt_id=uuid4(),
            node_type=create.node_type,
            template_text=create.template_text,
            input_schema_id=None,
            output_schema_id=None,
            version=1,
            frozen_hash=PromptService._calculate_frozen_hash(create.template_text),
            is_active=True,
            description=create.description,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = MagicMock(spec=PromptRepository)
        repo.get_active_prompt = AsyncMock(return_value=None)
        repo.create_prompt = AsyncMock(return_value=created_prompt)

        service = PromptService(repository=repo)
        result = await service.create_or_update_prompt(create)

        assert result is not None
        repo.create_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_service_rejects_empty_template(self):
        create = NodePromptCreate(
            node_type=NodeType.IntentToolSelectionNode.value,
            template_text="",
            description="Test",
        )

        repo = MagicMock(spec=PromptRepository)
        service = PromptService(repository=repo)

        with pytest.raises(Exception):
            await service.create_or_update_prompt(create)
