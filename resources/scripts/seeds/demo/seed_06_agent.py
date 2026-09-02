from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select, update

from domain.agents.schemas.agents import PersonaConfig
from domain.common.schemas.versioning import VersionStatus
from infra.database import get_db
from infra.database.models.agent.agent import Agent
from infra.database.models.agent.agent_version import AgentVersion

from seeds.demo.ids import (
    AGENT_DEMO_ID,
    AGENT_VERSION_V1_ID,
    POLICY_VERSION_V1_ID,
    PRINCIPAL_SYSTEM,
    RAG_CONFIG_DEMO_ID,
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
                name="Demo Assistant",
            )
            session.add(agent)
            await session.commit()

        result = await session.execute(
            select(AgentVersion).where(
                AgentVersion.agent_version_id == AGENT_VERSION_V1_ID
            )
        )
        agent_version = result.scalar_one_or_none()

        persona_config = PersonaConfig.model_validate(
            {
                "language": "en_US",
                "tone": "professional",
                "style": "concise",
                "rules": [
                    "Never invent data; work only with data available in the system.",
                    "State explicitly when information is not available.",
                    "Confirm data whenever there is meaningful ambiguity.",
                    "Do not assume context that was not provided.",
                    "Do not promise features that do not exist.",
                ],
                "max_response_length": 500,
            }
        ).model_dump(mode="json")

        if agent_version is None:
            agent_version = AgentVersion(
                agent_version_id=AGENT_VERSION_V1_ID,
                agent_id=AGENT_DEMO_ID,
                ai_execution_policy_version_id=POLICY_VERSION_V1_ID,
                rag_config_id=RAG_CONFIG_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                description="Demo Assistant v1.0.0",
                persona_config=persona_config,
                system_prompt='''You are a demo assistant that records and looks up personal expenses. Before taking any action or producing a response, plan and validate your reasoning internally in a structured way.

Data integrity and risk
   Rely exclusively on data provided in the conversation, relevant history, and explicitly confirmed information.
   Never assume missing values and never make up guesses.
   If a required piece of data is missing, state plainly that it is not available.
   If the missing data is not critical, proceed with what is available.

Operating rules:
* Reply in the language the user wrote in.
* Keep responses concise (2-3 sentences).
* Use assertive language: "Done", "Recorded", "Updated".
* Keep a professional, clear, and objective tone.
'''
            )
            session.add(agent_version)
            await session.commit()
        elif agent_version.rag_config_id is None:
            agent_version.rag_config_id = RAG_CONFIG_DEMO_ID
            await session.commit()

        await session.execute(
            update(AgentVersion)
            .where(
                AgentVersion.agent_id == AGENT_DEMO_ID,
                AgentVersion.agent_version_id != AGENT_VERSION_V1_ID,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(AgentVersion)
            .where(
                AgentVersion.agent_id == AGENT_DEMO_ID,
                AgentVersion.agent_version_id == AGENT_VERSION_V1_ID,
            )
            .values(
                is_active=True,
                activated_at=datetime.now(timezone.utc),
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="Bootstrap seed - initial activation",
            )
        )
        await session.commit()
