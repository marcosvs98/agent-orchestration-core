from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from infra.database import get_db
from infra.database.models.agent.agent import Agent
from infra.database.models.agent.agent_version import AgentVersion
from infra.database.models.agent.active_agent_version import ActiveAgentVersion

from seeds.demo.ids import (
    AGENT_DEMO_ID,
    AGENT_VERSION_V1_ID,
    POLICY_VERSION_V1_ID,
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
)


async def seed_agent() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Agent).where(Agent.agent_id == AGENT_DEMO_ID)
        )
        agent = result.scalar_one_or_none()

        if agent is None:
            agent = Agent(
                agent_id=AGENT_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="Assistente Financeiro",
            )
            session.add(agent)
            await session.commit()

        result = await session.execute(
            select(AgentVersion).where(
                AgentVersion.agent_version_id == AGENT_VERSION_V1_ID
            )
        )
        agent_version = result.scalar_one_or_none()

        persona_config = {
            "language": "pt_BR",
            "tone": "professional",
            "style": "concise",
            "rules": [
                "Não invente informações",
                "Confirme dados críticos antes de executar ações",
            ],
            "max_response_length": 500,
        }

        if agent_version is None:
            agent_version = AgentVersion(
                agent_version_id=AGENT_VERSION_V1_ID,
                agent_id=AGENT_DEMO_ID,
                ai_execution_policy_version_id=POLICY_VERSION_V1_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                description="Agent demo v1.0.0",
                persona_config=persona_config,
            )
            session.add(agent_version)
            await session.commit()

        result = await session.execute(
            select(ActiveAgentVersion).where(
                ActiveAgentVersion.agent_id == AGENT_DEMO_ID
            )
        )
        active_version = result.scalar_one_or_none()

        if active_version is None:
            active_version = ActiveAgentVersion(
                agent_id=AGENT_DEMO_ID,
                agent_version_id=AGENT_VERSION_V1_ID,
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="Bootstrap seed - ativação inicial",
            )
            session.add(active_version)
            await session.commit()
