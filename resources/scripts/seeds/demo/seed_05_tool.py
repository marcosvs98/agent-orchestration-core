from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.tools.schemas.openapi_types import OpenAPISpec
from domain.tools.schemas.tool_config_types import ToolConfigConfig
from domain.tools.services.openapi_parser import OpenAPIParser
from infra.database import get_db
from infra.database.models.tool.tool import Tool
from infra.database.models.tool.tool_config import ToolConfig

from seeds.demo.ids import (
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


async def seed_tool() -> None:
    openapi_path = Path(__file__).parent / "openapi" / "demo_api.json"
    if not openapi_path.exists():
        await _create_basic_tool()
        return

    async with get_db() as session:
        with open(openapi_path, "r") as f:
            openapi_spec = json.load(f)

        parser = OpenAPIParser()
        parsed_spec = OpenAPISpec(
            title=openapi_spec.get("info", {}).get("title", "Demo API"),
            version=openapi_spec.get("info", {}).get("version", "1.0.0"),
            paths=openapi_spec.get("paths", {}),
            schemas=openapi_spec.get("components", {}).get("schemas", {}),
            openapi_version=openapi_spec.get("openapi"),
            servers=openapi_spec.get("servers", []),
            components=openapi_spec.get("components", {}),
        )
        operations = parser.extract_operations(parsed_spec)

        if not operations:
            await _create_basic_tool()
            return

        result = await session.execute(select(Tool).where(Tool.tool_id == TOOL_DEMO_ID))
        tool = result.scalar_one_or_none()
        if tool is None:
            tool = Tool(tool_id=TOOL_DEMO_ID, name="createExpense")
            session.add(tool)
            await session.commit()

        result = await session.execute(select(ToolConfig).where(ToolConfig.tool_config_id == TOOL_CONFIG_DEMO_ID))
        existing_config = result.scalar_one_or_none()
        if existing_config:
            return

        result = await session.execute(
            select(ToolConfig).where(
                ToolConfig.tool_id == TOOL_DEMO_ID,
                ToolConfig.tenant_id == TENANT_DEMO_ID,
                ToolConfig.version_major == 1,
                ToolConfig.version_minor == 0,
                ToolConfig.version_patch == 0,
            )
        )
        existing_by_version = result.scalar_one_or_none()
        if existing_by_version:
            return

        base_url = "http://localhost:3001"
        servers = parsed_spec.servers if hasattr(parsed_spec, "servers") else []
        if servers and isinstance(servers, list) and len(servers) > 0:
            server_url = servers[0].get("url", "")
            if server_url:
                base_url = server_url

        op = operations[0]
        path = op.get("path", "")
        full_url = f"{base_url}{path}" if base_url else path

        tool_config_dict = ToolConfigConfig(
            url=full_url,
            method=op.get("method", "POST"),
            request_schema=op.get("request_schema", {}),
            response_schema=op.get("response_schema", {}),
            operation_id=op.get("operation_id", "createExpense"),
        )

        tool_config = ToolConfig(
            tool_config_id=TOOL_CONFIG_DEMO_ID,
            tool_id=TOOL_DEMO_ID,
            tenant_id=TENANT_DEMO_ID,
            config=tool_config_dict,
            status=VersionStatus.PUBLISHED.value,
            version_major=1,
            version_minor=0,
            version_patch=0,
            schema_version=1,
        )
        session.add(tool_config)
        await session.commit()


async def _create_basic_tool() -> None:
    async with get_db() as session:
        result = await session.execute(select(Tool).where(Tool.tool_id == TOOL_DEMO_ID))
        tool = result.scalar_one_or_none()
        if tool is None:
            tool = Tool(tool_id=TOOL_DEMO_ID, name="createExpense")
            session.add(tool)
            await session.commit()

        result = await session.execute(select(ToolConfig).where(ToolConfig.tool_config_id == TOOL_CONFIG_DEMO_ID))
        tool_config = result.scalar_one_or_none()
        if tool_config is None:
            tool_config_dict = ToolConfigConfig(
                url="http://localhost:3000/createExpense",
                method="POST",
                request_schema={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "bank_name": {"type": "string"},
                        "account_alias": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "payment_method": {"type": "string"},
                        "date": {"type": "string", "format": "date-time"},
                        "notes": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["amount", "currency", "bank_name", "account_alias", "description", "category", "payment_method", "date"],
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "expense_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                operation_id="createExpense",
            )

            tool_config = ToolConfig(
                tool_config_id=TOOL_CONFIG_DEMO_ID,
                tool_id=TOOL_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                config=tool_config_dict,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                schema_version=1,
            )
            session.add(tool_config)
            await session.commit()
