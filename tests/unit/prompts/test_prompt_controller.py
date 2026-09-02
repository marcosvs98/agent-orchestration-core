from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.prompts.controllers.prompt_controller import PromptController
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException
from utils.auth import AuthContext


class TestPromptController:
    @pytest.mark.asyncio
    async def test_get_prompt_returns_prompt_when_found(self):
        prompt_id = uuid4()
        prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=NodeType.ToolResolver.value,
            template_text="Test prompt",
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

        service = MagicMock(spec=PromptService)
        service.get_prompt = AsyncMock(return_value=prompt)
        controller = PromptController(service=service)

        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="test",
            scopes={"admin"},
            token_issuer="test",
            token_audience="test",
            expires_at=9999999999,
        )

        result = await controller.get_prompt(
            node_type=NodeType.ToolResolver.value,
            _=auth,
        )

        assert result is not None
        assert result.prompt_id == prompt_id
        service.get_prompt.assert_called_once_with(NodeType.ToolResolver.value)

    @pytest.mark.asyncio
    async def test_get_prompt_raises_when_not_found(self):
        service = MagicMock(spec=PromptService)
        service.get_prompt = AsyncMock(return_value=None)
        controller = PromptController(service=service)

        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="test",
            scopes={"admin"},
            token_issuer="test",
            token_audience="test",
            expires_at=9999999999,
        )

        with pytest.raises(DomainValidationException):
            await controller.get_prompt(
                node_type=NodeType.ToolResolver.value,
                _=auth,
            )

    @pytest.mark.asyncio
    async def test_create_or_update_prompt_creates_prompt(self):
        prompt_id = uuid4()
        create = NodePromptCreate(
            node_type=NodeType.ToolResolver.value,
            template_text="New prompt",
            description="Test",
        )

        created_prompt = NodePrompt(
            prompt_id=prompt_id,
            node_type=create.node_type,
            template_text=create.template_text,
            input_schema=None,
            output_schema=None,
            version=1,
            frozen_hash="hash123",
            is_active=True,
            description=create.description,
            created_by="test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        service = MagicMock(spec=PromptService)
        service.create_or_update_prompt = AsyncMock(return_value=created_prompt)
        controller = PromptController(service=service)

        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="test",
            scopes={"admin"},
            token_issuer="test",
            token_audience="test",
            expires_at=9999999999,
        )

        result = await controller.create_or_update_prompt(
            node_type=NodeType.ToolResolver.value,
            create=create,
            auth=auth,
        )

        assert result is not None
        assert result.prompt_id == prompt_id
        service.create_or_update_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_or_update_prompt_raises_when_node_type_mismatch(self):
        create = NodePromptCreate(
            node_type=NodeType.ToolInputFiller.value,
            template_text="Prompt",
        )

        service = MagicMock(spec=PromptService)
        controller = PromptController(service=service)

        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="test",
            scopes={"admin"},
            token_issuer="test",
            token_audience="test",
            expires_at=9999999999,
        )

        with pytest.raises(DomainValidationException):
            await controller.create_or_update_prompt(
                node_type=NodeType.ToolResolver.value,
                create=create,
                auth=auth,
            )

    @pytest.mark.asyncio
    async def test_delete_prompt_deactivates_prompt(self):
        service = MagicMock(spec=PromptService)
        service.deactivate_prompt = AsyncMock()
        controller = PromptController(service=service)

        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="test",
            scopes={"admin"},
            token_issuer="test",
            token_audience="test",
            expires_at=9999999999,
        )

        await controller.delete_prompt(
            node_type=NodeType.ToolResolver.value,
            auth=auth,
        )

        service.deactivate_prompt.assert_called_once_with(
            NodeType.ToolResolver.value,
            tenant_id=auth.tenant_id,
        )
