from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.flows.repositories.flows_repository import FlowsRepository
from infra.database import DatabaseConnection


class TestFlowsRepository:
    @pytest.fixture
    def database_connection(self):
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection):
        return FlowsRepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_create_flow_persists_created_by(
        self, repository, database_connection
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        name = "Test Flow"
        created_by = "user-123"

        mock_session = MagicMock()
        mock_instance = SimpleNamespace(flow_id=flow_id, name=name, created_by=created_by)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.create_flow(
            tenant_id=tenant_id, name=name, created_by=created_by
        )

        mock_session.add.assert_called_once()
        added_instance = mock_session.add.call_args[0][0]
        assert added_instance.tenant_id == tenant_id
        assert added_instance.name == name
        assert added_instance.created_by == created_by
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_persists_description_and_tags(
        self, repository, database_connection
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        name = "Test Flow"
        description = "Flow description"
        tags = ["tag1", "tag2"]
        created_by = "user-123"

        mock_session = MagicMock()
        mock_instance = SimpleNamespace(
            flow_id=flow_id,
            name=name,
            description=description,
            tags=tags,
            created_by=created_by
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.create_flow(
            tenant_id=tenant_id,
            name=name,
            description=description,
            tags=tags,
            created_by=created_by
        )

        mock_session.add.assert_called_once()
        added_instance = mock_session.add.call_args[0][0]
        assert added_instance.name == name
        assert added_instance.description == description
        assert added_instance.tags == tags
        assert added_instance.created_by == created_by

    @pytest.mark.asyncio
    async def test_create_flow_persists_name_correctly(
        self, repository, database_connection
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        name = "My Flow"
        created_by = "admin-456"

        mock_session = MagicMock()
        mock_instance = SimpleNamespace(flow_id=flow_id, name=name, created_by=created_by)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.create_flow(
            tenant_id=tenant_id, name=name, created_by=created_by
        )

        mock_session.add.assert_called_once()
        added_instance = mock_session.add.call_args[0][0]
        assert added_instance.name == name
        assert added_instance.created_by == created_by
