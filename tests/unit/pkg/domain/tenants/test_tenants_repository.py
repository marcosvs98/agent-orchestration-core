from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tenants.repositories.tenants_repository import TenantsRepository
from infra.database import DatabaseConnection


class TestTenantsRepository:
    @pytest.fixture
    def database_connection(self):
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection):
        return TenantsRepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_get_tenant_by_external_id_returns_tenant_when_exists(
        self, repository, database_connection
    ):
        external_id = uuid4()
        tenant_id = uuid4()
        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=external_id,
            name="Test Tenant",
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_tenant)
        mock_session.execute = AsyncMock(return_value=mock_result)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await repository.get_tenant_by_external_id(external_id)

        assert result == mock_tenant
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tenant_by_external_id_returns_none_when_not_exists(
        self, repository, database_connection
    ):
        external_id = uuid4()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await repository.get_tenant_by_external_id(external_id)

        assert result is None
        mock_session.execute.assert_called_once()
