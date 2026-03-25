import hashlib
import re
import secrets
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select, update

from domain.mcp_registry.schemas.mcp_registry import (
    McpBindingState,
    McpServerBuildSpec,
    McpServerToolBinding,
)
from infra.database import DatabaseConnection
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
from infra.database.models.prompts.user_prompt import UserPrompt as UserPromptModel
from infra.database.models.rag.vector_store import VectorStore as VectorStoreModel
from infra.database.models.tool.tool import Tool as ToolModel
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel
from infra.database.models.flow.flow_snapshot import FlowSnapshot as FlowSnapshotModel
from infra.database.models.flow.flow_deployment import (
    FlowDeployment as FlowDeploymentModel,
)
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.flow import Flow as FlowModel


def _mcp_prompt_slug(title: str, user_prompt_id: UUID) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", (title or "").strip()).strip("_").lower()
    if not base:
        base = "user_prompt"
    base = base[:48]
    return f"{base}_{str(user_prompt_id).replace('-', '')[:8]}"


class McpRegistryRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def validate_tool_configs_tenant(
        self, *, tenant_id: UUID, tool_config_ids: list[UUID]
    ) -> bool:
        if not tool_config_ids:
            return True
        async with self.db.get_session() as session:
            stmt = select(ToolConfigModel.tool_config_id).where(
                ToolConfigModel.tool_config_id.in_(tool_config_ids),
                ToolConfigModel.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            found = {row[0] for row in result.fetchall()}
            return len(found) == len(set(tool_config_ids))

    async def validate_vector_stores_tenant(
        self, *, tenant_id: UUID, vector_store_ids: list[UUID]
    ) -> bool:
        if not vector_store_ids:
            return True
        async with self.db.get_session() as session:
            stmt = select(VectorStoreModel.vector_store_id).where(
                VectorStoreModel.vector_store_id.in_(vector_store_ids),
                VectorStoreModel.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            found = {row[0] for row in result.fetchall()}
            return len(found) == len(set(vector_store_ids))

    async def validate_user_prompts_tenant(
        self, *, tenant_id: UUID, user_prompt_ids: list[UUID]
    ) -> bool:
        if not user_prompt_ids:
            return True
        async with self.db.get_session() as session:
            stmt = select(UserPromptModel.user_prompt_id).where(
                UserPromptModel.user_prompt_id.in_(user_prompt_ids),
                UserPromptModel.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            found = {row[0] for row in result.fetchall()}
            return len(found) == len(set(user_prompt_ids))

    async def list_servers_by_tenant(self, *, tenant_id: UUID) -> list[McpServer]:
        async with self.db.get_session() as session:
            stmt = (
                select(McpServer)
                .where(McpServer.tenant_id == tenant_id)
                .order_by(McpServer.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_server_by_tenant(
        self, *, tenant_id: UUID, mcp_server_id: UUID
    ) -> McpServer | None:
        async with self.db.get_session() as session:
            stmt = select(McpServer).where(
                McpServer.tenant_id == tenant_id,
                McpServer.mcp_server_id == mcp_server_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_server_binding_ids(
        self, *, mcp_server_id: UUID
    ) -> tuple[list[UUID], list[UUID], list[UUID]]:
        async with self.db.get_session() as session:
            t_stmt = select(McpServerTool.tool_config_id).where(
                McpServerTool.mcp_server_id == mcp_server_id
            )
            v_stmt = select(McpServerVectorStore.vector_store_id).where(
                McpServerVectorStore.mcp_server_id == mcp_server_id
            )
            p_stmt = select(McpServerUserPrompt.user_prompt_id).where(
                McpServerUserPrompt.mcp_server_id == mcp_server_id
            )
            tool_ids = sorted(
                (r[0] for r in (await session.execute(t_stmt)).fetchall()),
                key=lambda x: str(x),
            )
            vector_store_ids = sorted(
                (r[0] for r in (await session.execute(v_stmt)).fetchall()),
                key=lambda x: str(x),
            )
            user_prompt_ids = sorted(
                (r[0] for r in (await session.execute(p_stmt)).fetchall()),
                key=lambda x: str(x),
            )
            return tool_ids, vector_store_ids, user_prompt_ids

    async def create_server_with_bindings(
        self,
        *,
        tenant_id: UUID,
        name: str,
        tool_config_ids: list[UUID],
        vector_store_ids: list[UUID],
        user_prompt_ids: list[UUID],
        flow_snapshot_id: UUID | None,
        flow_deployment_id: UUID | None,
    ) -> tuple[McpServer, str]:
        raw_key = secrets.token_urlsafe(32)
        key_hash = self.hash_api_key(raw_key)
        key_prefix = raw_key[:8] if len(raw_key) >= 8 else raw_key
        async with self.db.get_session() as session:
            server = McpServer(
                tenant_id=tenant_id,
                name=name,
                status="ACTIVE",
                flow_snapshot_id=flow_snapshot_id,
                flow_deployment_id=flow_deployment_id,
            )
            session.add(server)
            await session.flush()
            for tid in tool_config_ids:
                session.add(
                    McpServerTool(
                        mcp_server_id=server.mcp_server_id,
                        tool_config_id=tid,
                    )
                )
            for vid in vector_store_ids:
                session.add(
                    McpServerVectorStore(
                        mcp_server_id=server.mcp_server_id,
                        vector_store_id=vid,
                    )
                )
            for pid in user_prompt_ids:
                session.add(
                    McpServerUserPrompt(
                        mcp_server_id=server.mcp_server_id,
                        user_prompt_id=pid,
                    )
                )
            await session.execute(
                update(McpServerCredential)
                .where(
                    McpServerCredential.mcp_server_id == server.mcp_server_id,
                    McpServerCredential.revoked_at.is_(None),
                )
                .values(revoked_at=sa.func.now())
            )
            session.add(
                McpServerCredential(
                    mcp_server_id=server.mcp_server_id,
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                )
            )
            await session.commit()
            await session.refresh(server)
            return server, raw_key

    async def validate_flow_snapshot_tenant(
        self, *, tenant_id: UUID, flow_snapshot_id: UUID | None
    ) -> bool:
        if flow_snapshot_id is None:
            return True
        async with self.db.get_session() as session:
            stmt = (
                select(FlowSnapshotModel.flow_snapshot_id)
                .join(
                    FlowVersionModel,
                    FlowVersionModel.flow_version_id
                    == FlowSnapshotModel.flow_version_id,
                )
                .join(FlowModel, FlowModel.flow_id == FlowVersionModel.flow_id)
                .where(
                    FlowSnapshotModel.flow_snapshot_id == flow_snapshot_id,
                    FlowModel.tenant_id == tenant_id,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def validate_flow_deployment_tenant(
        self, *, tenant_id: UUID, flow_deployment_id: UUID | None
    ) -> bool:
        if flow_deployment_id is None:
            return True
        async with self.db.get_session() as session:
            stmt = (
                select(FlowDeploymentModel.flow_deployment_id)
                .join(FlowModel, FlowModel.flow_id == FlowDeploymentModel.flow_id)
                .where(
                    FlowDeploymentModel.flow_deployment_id == flow_deployment_id,
                    FlowModel.tenant_id == tenant_id,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def verify_api_key_and_load_bindings(
        self, *, mcp_server_id: UUID, api_key: str
    ) -> McpBindingState | None:
        if not api_key.strip():
            return None
        want_hash = self.hash_api_key(api_key)
        async with self.db.get_session() as session:
            stmt = (
                select(McpServerCredential, McpServer)
                .join(
                    McpServer,
                    McpServer.mcp_server_id == McpServerCredential.mcp_server_id,
                )
                .where(
                    McpServerCredential.mcp_server_id == mcp_server_id,
                    McpServerCredential.revoked_at.is_(None),
                    McpServer.status == "ACTIVE",
                )
            )
            result = await session.execute(stmt)
            rows = result.all()
            cred_row = None
            server_row = None
            for cred, srv in rows:
                if secrets.compare_digest(cred.key_hash, want_hash):
                    cred_row = cred
                    server_row = srv
                    break
            if cred_row is None or server_row is None:
                return None
            t_stmt = select(McpServerTool.tool_config_id).where(
                McpServerTool.mcp_server_id == mcp_server_id
            )
            v_stmt = select(McpServerVectorStore.vector_store_id).where(
                McpServerVectorStore.mcp_server_id == mcp_server_id
            )
            p_stmt = select(McpServerUserPrompt.user_prompt_id).where(
                McpServerUserPrompt.mcp_server_id == mcp_server_id
            )
            tools = {r[0] for r in (await session.execute(t_stmt)).fetchall()}
            vss = {r[0] for r in (await session.execute(v_stmt)).fetchall()}
            ups = {r[0] for r in (await session.execute(p_stmt)).fetchall()}
            return McpBindingState(
                tenant_id=server_row.tenant_id,
                mcp_server_id=mcp_server_id,
                tool_config_ids=frozenset(tools),
                vector_store_ids=frozenset(vss),
                user_prompt_ids=frozenset(ups),
                flow_snapshot_id=server_row.flow_snapshot_id,
                flow_deployment_id=server_row.flow_deployment_id,
            )

    async def fetch_mcp_server_build_spec(
        self, state: McpBindingState
    ) -> McpServerBuildSpec:
        tool_rows: list[McpServerToolBinding] = []
        used_names: dict[str, int] = {}
        async with self.db.get_session() as session:
            if state.tool_config_ids:
                stmt = (
                    select(
                        ToolConfigModel.tool_config_id,
                        ToolModel.name,
                        ToolConfigModel.config,
                    )
                    .join(
                        ToolModel,
                        ToolModel.tool_id == ToolConfigModel.tool_id,
                    )
                    .where(
                        ToolConfigModel.tool_config_id.in_(list(state.tool_config_ids)),
                        ToolConfigModel.tenant_id == state.tenant_id,
                    )
                )
                result = await session.execute(stmt)
                for tcid, tname, cfg in result.all():
                    cfg = cfg or {}
                    desc = (
                        str(cfg.get("description") or cfg.get("summary") or "")
                    ).strip()
                    base = (tname or "").strip() or f"tool_{str(tcid)[:8]}"
                    if base not in used_names:
                        used_names[base] = 0
                        mcp_name = base
                    else:
                        mcp_name = f"{base}_{str(tcid).replace('-', '')[:8]}"
                    used_names[mcp_name] = 1
                    req = cfg.get("request_schema")
                    if isinstance(req, dict) and req.get("type") == "object":
                        request_schema = dict(req)
                    elif isinstance(req, dict) and "properties" in req:
                        request_schema = {"type": "object", **req}
                    else:
                        request_schema = {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True,
                        }
                    resp = cfg.get("response_schema")
                    response_schema = (
                        dict(resp)
                        if isinstance(resp, dict) and resp.get("type") == "object"
                        else None
                    )
                    tool_rows.append(
                        McpServerToolBinding(
                            tool_config_id=tcid,
                            mcp_name=mcp_name,
                            description=desc,
                            request_schema=request_schema,
                            response_schema=response_schema,
                        )
                    )
            prompt_rows: list[tuple[UUID, str, str, str]] = []
            if state.user_prompt_ids:
                p_stmt = select(UserPromptModel).where(
                    UserPromptModel.user_prompt_id.in_(list(state.user_prompt_ids)),
                    UserPromptModel.tenant_id == state.tenant_id,
                )
                pres = await session.execute(p_stmt)
                slugs: dict[str, int] = {}
                for up in pres.scalars().all():
                    slug = _mcp_prompt_slug(up.title, up.user_prompt_id)
                    if slug in slugs:
                        slug = f"{slug}_{str(up.user_prompt_id).replace('-', '')[:8]}"
                    slugs[slug] = 1
                    prompt_rows.append(
                        (up.user_prompt_id, slug, up.title or "", up.content or "")
                    )
            vss = tuple(sorted(state.vector_store_ids, key=lambda x: str(x)))
            tool_rows.sort(key=lambda b: str(b.tool_config_id))
            prompt_rows.sort(key=lambda x: str(x[0]))
        return McpServerBuildSpec(
            tenant_id=state.tenant_id,
            mcp_server_id=state.mcp_server_id,
            tools=tuple(tool_rows),
            vector_store_ids=vss,
            prompts=tuple(prompt_rows),
            flow_snapshot_id=state.flow_snapshot_id,
            flow_deployment_id=state.flow_deployment_id,
        )
