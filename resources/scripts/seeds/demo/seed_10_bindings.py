from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
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
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_CLARIFICATION_ID,
    TOOL_CONFIG_DEMO_ID,
)


async def seed_bindings() -> None:
    async with get_db() as session:
        nodes = [NODE_INTENT_ID, NODE_SLOT_ID, NODE_RESPONSE_ID, NODE_CLARIFICATION_ID]

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

        result = await session.execute(
            select(AgentVersionToolBinding).where(
                AgentVersionToolBinding.agent_version_id == AGENT_VERSION_V1_ID,
                AgentVersionToolBinding.tool_config_id == TOOL_CONFIG_DEMO_ID,
            )
        )
        tool_binding = result.scalar_one_or_none()

        if tool_binding is None:
            tool_binding = AgentVersionToolBinding(
                agent_version_id=AGENT_VERSION_V1_ID,
                tool_config_id=TOOL_CONFIG_DEMO_ID,
            )
            session.add(tool_binding)

        await session.commit()
