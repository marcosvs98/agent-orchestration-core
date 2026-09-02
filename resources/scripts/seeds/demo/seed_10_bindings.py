from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.agent.node_agent_binding import NodeAgentBinding
from infra.database.models.tool.agent_version_tool_binding import (
    AgentVersionToolBinding,
)

from seeds.demo.ids import (
    AGENT_VERSION_V1_ID,
    NODE_CLARIFICATION_ID,
    NODE_CLARIFICATION_INTENT_ID,
    NODE_INPUT_MODERATION_ID,
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_SELECTION_ID,
    NODE_FALLBACK_SLA_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)
from seeds.demo.demo_tool_catalog import fetch_demo_tool_rows


async def seed_bindings() -> None:
    rows = await fetch_demo_tool_rows(
        demo_tool_id=TOOL_DEMO_ID,
        demo_tool_config_id=TOOL_CONFIG_DEMO_ID,
    )
    tool_config_ids = [r["tool_config_id"] for r in rows]
    async with get_db() as session:
        nodes = [
            NODE_INPUT_MODERATION_ID,
            NODE_INTENT_ID,
            NODE_SLOT_ID,
            NODE_RESPONSE_ID,
            NODE_CLARIFICATION_ID,
            NODE_CLARIFICATION_INTENT_ID,
            NODE_TOOL_SELECTION_ID,
            NODE_FALLBACK_SLA_ID,
        ]

        for node_id in nodes:
            result = await session.execute(
                select(NodeAgentBinding).where(
                    NodeAgentBinding.node_id == node_id,
                    NodeAgentBinding.agent_version_id == AGENT_VERSION_V1_ID,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                binding = NodeAgentBinding(
                    node_id=node_id,
                    agent_version_id=AGENT_VERSION_V1_ID,
                )
                session.add(binding)

        for tcid in tool_config_ids:
            result = await session.execute(
                select(AgentVersionToolBinding).where(
                    AgentVersionToolBinding.agent_version_id == AGENT_VERSION_V1_ID,
                    AgentVersionToolBinding.tool_config_id == tcid,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    AgentVersionToolBinding(
                        agent_version_id=AGENT_VERSION_V1_ID,
                        tool_config_id=tcid,
                    )
                )

        await session.commit()
