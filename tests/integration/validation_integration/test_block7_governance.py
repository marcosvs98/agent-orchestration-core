from __future__ import annotations

import pytest

from infra.database.models.agent.agent_version import AgentVersion
from infra.database.models.flow.flow_version import FlowVersion
from resources.scripts.validation_seed import (
    AGENT_ID,
    AGENT_VERSION_ID,
    DRAFT_FLOW_VERSION_ID,
    FLOW_ID,
    FLOW_VERSION_ID,
)
from .evidence import text_block, write_markdown

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_publish_activate_and_pointer_governance(db_session) -> None:
    from sqlalchemy import select

    flow_result = await db_session.execute(
        select(FlowVersion).where(FlowVersion.flow_id == FLOW_ID, FlowVersion.is_active.is_(True))
    )
    active_flow_version = flow_result.scalar_one_or_none()
    published_version = await db_session.get(FlowVersion, FLOW_VERSION_ID)
    draft_version = await db_session.get(FlowVersion, DRAFT_FLOW_VERSION_ID)
    agent_result = await db_session.execute(
        select(AgentVersion).where(
            AgentVersion.agent_id == AGENT_ID, AgentVersion.is_active.is_(True)
        )
    )
    active_agent_version = agent_result.scalar_one_or_none()

    assert active_flow_version is not None
    assert published_version is not None and published_version.status == "PUBLISHED"
    assert draft_version is not None and draft_version.status == "DRAFT"
    assert active_flow_version.flow_version_id == FLOW_VERSION_ID
    assert (
        active_agent_version is not None
        and active_agent_version.agent_version_id == AGENT_VERSION_ID
    )

    diagram = (
        "### Flow runtime diagram\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "flowCreated[FlowCreated] --> flowRunning[FlowRunning]\n"
        "flowRunning --> flowWaiting[FlowWaiting]\n"
        "flowRunning --> flowCompleted[FlowCompleted]\n"
        "flowRunning --> flowFailed[FlowFailed]\n"
        "flowRunning --> flowEscalated[FlowEscalated]\n"
        "flowWaiting --> flowRunning\n"
        "flowWaiting --> flowFailed\n"
        "flowWaiting --> flowEscalated\n"
        "flowCompleted --> flowTerminal[Terminal]\n"
        "flowFailed --> flowTerminal\n"
        "flowEscalated --> flowTerminal\n"
        "```\n"
    )

    write_markdown(
        "runtime-execution-diagram.md",
        [
            diagram,
            text_block(
                "Governance pointers",
                "Active pointers reference immutable published versions; draft versions exist but stay inactive (publish != activate).",
            ),
        ],
    )
