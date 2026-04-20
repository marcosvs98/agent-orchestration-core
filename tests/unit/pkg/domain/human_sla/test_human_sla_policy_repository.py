from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.human_sla.repositories.human_sla_policy_repository import (
    HumanSLAPolicyRepository,
)
from infra.database import DatabaseConnection


class TestHumanSLAPolicyRepositoryResolvePolicy:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLAPolicyRepository:
        return HumanSLAPolicyRepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_returns_policy_when_active_exists(
        self, repository: HumanSLAPolicyRepository, database_connection: MagicMock
    ) -> None:
        tenant_id = uuid4()
        policy_id = uuid4()
        now = datetime.now(timezone.utc)
        policy_row = SimpleNamespace(
            human_sla_policy_id=policy_id,
            tenant_id=tenant_id,
            name="policy-a",
            node="ToolNode",
            fallback_reason="TOOL_FAILURE",
            initial_priority="high",
            target_response_hours=4,
            target_resolution_hours=24,
            active=True,
            created_at=now,
            updated_at=now,
        )
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=policy_row)
        mock_session.execute = AsyncMock(return_value=mock_result)
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.resolve_policy(
            tenant_id=tenant_id, node="ToolNode", fallback_reason="TOOL_FAILURE"
        )

        assert result is not None
        assert result.human_sla_policy_id == policy_id
        assert result.node == "ToolNode"
        assert result.fallback_reason == "TOOL_FAILURE"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_policy(
        self, repository: HumanSLAPolicyRepository, database_connection: MagicMock
    ) -> None:
        tenant_id = uuid4()
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

        result = await repository.resolve_policy(
            tenant_id=tenant_id, node="ToolNode", fallback_reason="LOW_CONFIDENCE"
        )

        assert result is None
        mock_session.execute.assert_called_once()


class TestHumanSLAPolicyRepositoryGetPolicyWithRules:
    @pytest.fixture
    def database_connection(self) -> MagicMock:
        db = MagicMock(spec=DatabaseConnection)
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def repository(self, database_connection: MagicMock) -> HumanSLAPolicyRepository:
        return HumanSLAPolicyRepository(database_connection=database_connection)

    @pytest.mark.asyncio
    async def test_returns_policy_with_rules_ordered_by_level(
        self, repository: HumanSLAPolicyRepository, database_connection: MagicMock
    ) -> None:
        policy_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)
        policy_row = SimpleNamespace(
            human_sla_policy_id=policy_id,
            tenant_id=tenant_id,
            name="policy-a",
            node="ToolNode",
            fallback_reason="TOOL_FAILURE",
            initial_priority="high",
            target_response_hours=4,
            target_resolution_hours=24,
            active=True,
            created_at=now,
            updated_at=now,
        )
        rule1 = SimpleNamespace(
            human_sla_escalation_rule_id=uuid4(),
            human_sla_policy_id=policy_id,
            level=1,
            trigger_after_hours=2,
            new_priority="urgent",
        )
        rule0 = SimpleNamespace(
            human_sla_escalation_rule_id=uuid4(),
            human_sla_policy_id=policy_id,
            level=0,
            trigger_after_hours=1,
            new_priority="high",
        )
        mock_session = MagicMock()
        result1 = MagicMock()
        result1.scalar_one_or_none = MagicMock(return_value=policy_row)
        result2 = MagicMock()
        result2.scalars.return_value.all = MagicMock(
            return_value=[rule0, rule1]
        )
        mock_session.execute = AsyncMock(side_effect=[result1, result2])
        database_connection.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        database_connection.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        result = await repository.get_policy_with_rules(human_sla_policy_id=policy_id)

        assert result is not None
        assert result.human_sla_policy_id == policy_id
        assert len(result.escalation_rules) == 2
        assert result.escalation_rules[0].level == 0
        assert result.escalation_rules[1].level == 1
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_policy_not_found(
        self, repository: HumanSLAPolicyRepository, database_connection: MagicMock
    ) -> None:
        policy_id = uuid4()
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

        result = await repository.get_policy_with_rules(
            human_sla_policy_id=policy_id
        )

        assert result is None
        mock_session.execute.assert_called_once()
