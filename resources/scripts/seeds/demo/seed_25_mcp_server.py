from __future__ import annotations

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import delete, func, select, update

from infra.database import get_db
from infra.database.models.mcp_registry.mcp_server import McpServer
from infra.database.models.mcp_registry.mcp_server_credential import (
    McpServerCredential,
)
from infra.database.models.mcp_registry.mcp_server_tool import McpServerTool
from infra.database.models.mcp_registry.mcp_server_user_prompt import (
    McpServerUserPrompt,
)
from infra.database.models.mcp_registry.mcp_server_vector_store import (
    McpServerVectorStore,
)

from domain.common.schemas.versioning import VersionStatus
from infra.database.models.tool.tool_config import ToolConfig

from seeds.demo.ids import (
    FLOW_DEPLOYMENT_DEFAULT_ID,
    FLOW_SNAPSHOT_V1_ID,
    MCP_SEED_DEMO_API_KEY,
    MCP_SERVER_DEMO_ID,
    TENANT_DEMO_ID,
    USER_PROMPT_DEMO_ID,
    VECTOR_STORE_DEMO_ID,
)


async def seed_mcp_server() -> None:
    key_hash = hashlib.sha256(MCP_SEED_DEMO_API_KEY.encode("utf-8")).hexdigest()
    key_prefix = (
        MCP_SEED_DEMO_API_KEY[:8]
        if len(MCP_SEED_DEMO_API_KEY) >= 8
        else MCP_SEED_DEMO_API_KEY
    )
    async with get_db() as session:
        result = await session.execute(
            select(McpServer).where(
                McpServer.mcp_server_id == MCP_SERVER_DEMO_ID
            )
        )
        srv = result.scalar_one_or_none()
        if srv is None:
            srv = McpServer(
                mcp_server_id=MCP_SERVER_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="demo-mcp-server",
                status="ACTIVE",
                flow_snapshot_id=FLOW_SNAPSHOT_V1_ID,
                flow_deployment_id=FLOW_DEPLOYMENT_DEFAULT_ID,
            )
            session.add(srv)
        else:
            srv.tenant_id = TENANT_DEMO_ID
            srv.name = "demo-mcp-server"
            srv.status = "ACTIVE"
            srv.flow_snapshot_id = FLOW_SNAPSHOT_V1_ID
            srv.flow_deployment_id = FLOW_DEPLOYMENT_DEFAULT_ID
            session.add(srv)
        await session.flush()
        await session.execute(
            delete(McpServerTool).where(
                McpServerTool.mcp_server_id == MCP_SERVER_DEMO_ID
            )
        )
        await session.execute(
            delete(McpServerVectorStore).where(
                McpServerVectorStore.mcp_server_id == MCP_SERVER_DEMO_ID
            )
        )
        await session.execute(
            delete(McpServerUserPrompt).where(
                McpServerUserPrompt.mcp_server_id == MCP_SERVER_DEMO_ID
            )
        )
        await session.execute(
            update(McpServerCredential)
            .where(
                McpServerCredential.mcp_server_id == MCP_SERVER_DEMO_ID,
                McpServerCredential.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )
        tool_configs = await session.execute(
            select(ToolConfig.tool_config_id).where(
                ToolConfig.tenant_id == TENANT_DEMO_ID,
                ToolConfig.status == VersionStatus.PUBLISHED.value,
            )
        )
        for (tool_config_id,) in tool_configs.all():
            session.add(
                McpServerTool(
                    mcp_server_id=MCP_SERVER_DEMO_ID,
                    tool_config_id=tool_config_id,
                )
            )
        session.add(
            McpServerVectorStore(
                mcp_server_id=MCP_SERVER_DEMO_ID,
                vector_store_id=VECTOR_STORE_DEMO_ID,
            )
        )
        session.add(
            McpServerUserPrompt(
                mcp_server_id=MCP_SERVER_DEMO_ID,
                user_prompt_id=USER_PROMPT_DEMO_ID,
            )
        )
        session.add(
            McpServerCredential(
                mcp_server_id=MCP_SERVER_DEMO_ID,
                key_hash=key_hash,
                key_prefix=key_prefix,
            )
        )
        await session.commit()
