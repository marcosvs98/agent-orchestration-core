from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.human_sla.repositories.human_sla_repository import HumanSLARepository
from domain.human_sla.schemas.sla_case import (
    SLAFallbackReason,
    SLACaseCreate,
    SLAStatus,
)
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


class TestHumanSLARepositoryCreateCase:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLARepository:
        return HumanSLARepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_persists_human_sla_policy_id_and_current_escalation_level(
        self, repository: HumanSLARepository, database_connection: MagicMock
    ) -> None:
        policy_id = uuid4()
        case_id = uuid4()
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        node_run_id = uuid4()
        case_create = SLACaseCreate(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            node_run_id=node_run_id,
            interaction_id=None,
            user_id="user-1",
            priority="high",
            fallback_reason=SLAFallbackReason.TOOL_FAILURE,
            opened_at=datetime.now(timezone.utc),
            sla_target_at=None,
            human_sla_policy_id=policy_id,
            current_escalation_level=1,
        )
        created_row = SimpleNamespace(
            sla_case_id=case_id,
            tenant_id=tenant_id,
            human_sla_policy_id=policy_id,
            current_escalation_level=1,
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock(return_value=None)
        insert_result = MagicMock()
        insert_result.scalar_one_or_none = MagicMock(return_value=case_id)
        select_result = MagicMock()
        select_result.scalar_one = MagicMock(return_value=created_row)
        mock_session.execute = AsyncMock(
            side_effect=[insert_result, select_result]
        )
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.create_case(case_create)

        assert result is not None
        assert result.sla_case_id == case_id
        assert result.human_sla_policy_id == policy_id
        assert result.current_escalation_level == 1
        assert mock_session.execute.await_count == 2


class TestHumanSLARepositoryUpdateCaseEscalation:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLARepository:
        return HumanSLARepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_calls_update_with_priority_and_level(
        self, repository: HumanSLARepository, database_connection: MagicMock
    ) -> None:
        sla_case_id = uuid4()
        tenant_id = uuid4()
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock(return_value=None)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        await repository.update_case_escalation(
            sla_case_id=sla_case_id,
            tenant_id=tenant_id,
            priority="urgent",
            level=2,
        )

        assert mock_session.execute.await_count == 1
        assert mock_session.commit.await_count == 1


class TestHumanSLARepositoryUpdateCaseSlaBreached:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLARepository:
        return HumanSLARepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_calls_update_with_sla_breached_true(
        self, repository: HumanSLARepository, database_connection: MagicMock
    ) -> None:
        sla_case_id = uuid4()
        tenant_id = uuid4()
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock(return_value=None)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        await repository.update_case_sla_breached(
            sla_case_id=sla_case_id, tenant_id=tenant_id
        )

        assert mock_session.execute.await_count == 1
        assert mock_session.commit.await_count == 1
