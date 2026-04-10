from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parents[4]
_src = _repo_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.tools.schemas.tool_config_types import ToolConfigConfig
from infra.database import get_db
from infra.database.models.tool.agent_version_tool_binding import (
    AgentVersionToolBinding,
)
from infra.database.models.tool.tool import Tool
from infra.database.models.tool.tool_config import ToolConfig

from seeds.demo.ids import (
    AGENT_VERSION_V1_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)
from seeds.demo.uora_platform_tool_ids import fetch_uora_platform_tool_rows

# Injected Bearer token at runtime from chat metadata (app-platform JWT).
_UORA_END_USER_AUTH_HEADERS: dict[str, Any] = {
    "Authorization": {
        "interaction_metadata_key": "uora_end_user_authorization",
    },
}


def _reconcile_http_tool_config_dict(cfg: object, exec_base: str) -> dict[str, Any]:
    """Idempotent: coherent base_url + url and Authorization → interaction_metadata_key."""
    if not isinstance(cfg, dict):
        return {}
    path = cfg.get("path")
    method = cfg.get("method")
    if not isinstance(path, str) or not path.strip():
        return dict(cfg)
    if not isinstance(method, str) or not method.strip():
        return dict(cfg)
    out = dict(cfg)
    path_norm = path if path.startswith("/") else f"/{path}"
    base = exec_base.strip().rstrip("/")
    out["base_url"] = base
    out["url"] = f"{base}{path_norm}" if base else path_norm
    headers = out.get("headers")
    if not isinstance(headers, dict):
        headers = {}
    else:
        headers = dict(headers)
    headers["Authorization"] = dict(_UORA_END_USER_AUTH_HEADERS["Authorization"])
    out["headers"] = headers
    return out


async def seed_tool() -> None:
    rows = await fetch_uora_platform_tool_rows(
        demo_tool_id=TOOL_DEMO_ID,
        demo_tool_config_id=TOOL_CONFIG_DEMO_ID,
    )
    allowed_tool_ids = {r["tool_id"] for r in rows}
    allowed_tc_ids = {r["tool_config_id"] for r in rows}
    async with get_db() as session:
        res_b = await session.execute(
            select(AgentVersionToolBinding).where(
                AgentVersionToolBinding.agent_version_id == AGENT_VERSION_V1_ID,
                AgentVersionToolBinding.tool_config_id.notin_(allowed_tc_ids),
            )
        )
        for b in res_b.scalars().all():
            await session.delete(b)

        res_tc_del = await session.execute(
            select(ToolConfig).where(
                ToolConfig.tenant_id == TENANT_DEMO_ID,
                ToolConfig.tool_config_id.notin_(allowed_tc_ids),
            )
        )
        for tc_del in res_tc_del.scalars().all():
            await session.delete(tc_del)

        res_all_tools = await session.execute(select(Tool.tool_id))
        for (tid,) in res_all_tools.all():
            if tid in allowed_tool_ids:
                continue
            res_ref = await session.execute(
                select(ToolConfig.tool_config_id).where(ToolConfig.tool_id == tid).limit(1)
            )
            if res_ref.scalar_one_or_none() is None:
                row_t = await session.get(Tool, tid)
                if row_t is not None:
                    await session.delete(row_t)

        for row in rows:
            tool_id = row["tool_id"]
            tc_id = row["tool_config_id"]
            op_id = row["operation_id"]
            tool_display = row["tool_name"]
            path = str(row["path"])
            path_norm = path if path.startswith("/") else (f"/{path}" if path else "")
            exec_base = str(row["execution_base_url"]).strip().rstrip("/")
            full_url = f"{exec_base}{path_norm}" if exec_base else path
            cfg = ToolConfigConfig(
                base_url=exec_base or None,
                url=full_url,
                path=row["path"],
                method=row["method"],
                request_schema=row["request_schema"],
                response_schema=row["response_schema"],
                operation_id=op_id,
                summary=row["summary"],
                description=row["description"],
                examples=row["examples"],
                rag_activation={
                    "tenant_knowledge": {"enabled": True},
                    "user_memory_vector": {"enabled": True, "filters_override": {}},
                },
                headers=dict(_UORA_END_USER_AUTH_HEADERS),
            )
            result = await session.execute(select(Tool).where(Tool.name == tool_display))
            same_name = result.scalar_one_or_none()
            if same_name is not None and same_name.tool_id != tool_id:
                await session.delete(same_name)

            result = await session.execute(select(Tool).where(Tool.tool_id == tool_id))
            tool = result.scalar_one_or_none()
            if tool is None:
                session.add(Tool(tool_id=tool_id, name=tool_display))
            elif tool.name != tool_display:
                tool.name = tool_display
                session.add(tool)

            result_cfg = await session.execute(
                select(ToolConfig).where(ToolConfig.tool_config_id == tc_id)
            )
            existing_cfg = result_cfg.scalar_one_or_none()
            if existing_cfg is not None:
                existing_cfg.tool_id = tool_id
                existing_cfg.config = cfg
                existing_cfg.status = VersionStatus.PUBLISHED.value
                session.add(existing_cfg)
                continue

            result_cfg_v = await session.execute(
                select(ToolConfig).where(
                    ToolConfig.tool_id == tool_id,
                    ToolConfig.tenant_id == TENANT_DEMO_ID,
                    ToolConfig.version_major == 1,
                    ToolConfig.version_minor == 0,
                    ToolConfig.version_patch == 0,
                )
            )
            old_semver = result_cfg_v.scalar_one_or_none()
            if old_semver is not None and old_semver.tool_config_id != tc_id:
                await session.delete(old_semver)

            session.add(
                ToolConfig(
                    tool_config_id=tc_id,
                    tool_id=tool_id,
                    tenant_id=TENANT_DEMO_ID,
                    config=cfg,
                    status=VersionStatus.PUBLISHED.value,
                    version_major=1,
                    version_minor=0,
                    version_patch=0,
                    schema_version=1,
                )
            )

        # Reconcile every published demo tool_config: fixes stale DBs (loopback url, missing headers)
        # without manual SQL. Safe because demo tenant only has OpenAPI HTTP tools from this seed.
        exec_base_final = str(rows[0]["execution_base_url"]).strip().rstrip("/")
        res_pub = await session.execute(
            select(ToolConfig).where(
                ToolConfig.tenant_id == TENANT_DEMO_ID,
                ToolConfig.status == VersionStatus.PUBLISHED.value,
            )
        )
        for tc in res_pub.scalars().all():
            tc.config = _reconcile_http_tool_config_dict(tc.config, exec_base_final)
            session.add(tc)

        await session.commit()
