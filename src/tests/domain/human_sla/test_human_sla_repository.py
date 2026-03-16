from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.human_sla.repositories.human_sla_repository import HumanSLARepository
from domain.human_sla.schemas.sla_case import SLAStatus
from infra.database import DatabaseConnection


class TestHumanSLARepositoryGetLastOpenCaseForSession:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLARepository:
        return HumanSLARepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_open_case(
        self, repository: HumanSLARepository, database_connection: MagicMock
    ) -> None:
        tenant_id = uuid4()
        session_id = uuid4()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.get_last_open_case_for_session(
            tenant_id=tenant_id, session_id=session_id
        )

        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_most_recent_open_case_for_session(
        self, repository: HumanSLARepository, database_connection: MagicMock
    ) -> None:
        tenant_id = uuid4()
        session_id = uuid4()
        open_case = SimpleNamespace(
            sla_case_id=uuid4(),
            tenant_id=tenant_id,
            session_id=session_id,
            status=SLAStatus.OPEN.value,
            priority="high",
        )
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=open_case)
        mock_session.execute = AsyncMock(return_value=mock_result)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.get_last_open_case_for_session(
            tenant_id=tenant_id, session_id=session_id
        )

        assert result is open_case
        assert result.status == SLAStatus.OPEN.value
        mock_session.execute.assert_called_once()
