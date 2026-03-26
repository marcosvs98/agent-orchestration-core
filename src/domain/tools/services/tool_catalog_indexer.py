from __future__ import annotations

import json
from uuid import UUID

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagDocumentCreate
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.tools.schemas.tool_discovery import ToolCatalogDocument


class ToolCatalogIndexer:
    def __init__(
        self,
        rag_runtime_service: RagRuntimeService,
        rag_repository: RagRepository,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.rag_runtime_service = rag_runtime_service
        self.rag_repository = rag_repository
        self.tracer = tracer

    def build_document(
        self,
        *,
        tool_id: UUID,
        tool_config_id: UUID,
        tool_name: str | None,
        config: dict[str, object] | None,
        version: str,
    ) -> ToolCatalogDocument:
        config_data = config or {}
        return ToolCatalogDocument(
            tool_id=tool_id,
            tool_config_id=tool_config_id,
            tool_name=tool_name,
            operation_id=self._as_str(config_data.get("operation_id")),
            method=self._as_str(config_data.get("method")),
            path=self._extract_path(config_data),
            summary=self._as_str(config_data.get("summary")),
            description=self._as_str(config_data.get("description")),
            request_schema=self._as_dict(config_data.get("request_schema")),
            response_schema=self._as_dict(config_data.get("response_schema")),
            examples=self._as_examples(config_data.get("examples")),
            version=version,
        )

    async def index_document(
        self, *, tenant_id: UUID, document: ToolCatalogDocument
    ) -> bool:
        rag_config = await self._select_rag_config(tenant_id=tenant_id)
        if rag_config is None:
            return False
        payload = self._compose_payload(document)

        await self.rag_runtime_service.ingest_document(
            tenant_id=tenant_id,
            rag_config_id=rag_config.rag_config_id,
            document=payload,
        )
        return True

    async def _select_rag_config(self, *, tenant_id: UUID):
        configs = await self.rag_repository.list_rag_configs(
            tenant_id=tenant_id,
            status_filter=[VersionStatus.PUBLISHED.value],
            limit=1,
        )
        if not configs:
            return None
        return configs[0]

    def _compose_payload(self, document: ToolCatalogDocument) -> RagDocumentCreate:
        content_parts = [
            f"tool_name: {document.tool_name or ''}",
            f"operation_id: {document.operation_id or ''}",
            f"method: {document.method or ''}",
            f"path: {document.path or ''}",
            f"summary: {document.summary or ''}",
            f"description: {document.description or ''}",
            "request_schema:",
            json.dumps(document.request_schema, ensure_ascii=True, sort_keys=True),
            "response_schema:",
            json.dumps(document.response_schema, ensure_ascii=True, sort_keys=True),
            "examples:",
            json.dumps(document.examples, ensure_ascii=True),
        ]
        metadata = {
            "scope": "TENANT_KNOWLEDGE",
            "category": "TOOL_CATALOG",
            "tool_id": str(document.tool_id),
            "tool_config_id": str(document.tool_config_id),
            "tool_name": document.tool_name or "",
            "operation_id": document.operation_id,
            "method": document.method,
            "path": document.path,
            "tool_intent": self._derive_tool_intent(document.method),
        }
        return RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            content="\n".join(content_parts),
            version=document.version,
            metadata=metadata,
        )

    def _as_str(self, value: object | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def _as_dict(self, value: object | None) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        return {}

    def _as_examples(self, value: object | None) -> list[str]:
        if not isinstance(value, list):
            return []
        examples: list[str] = []
        for item in value:
            if item is None:
                continue
            examples.append(str(item))
        return examples

    def _derive_tool_intent(self, method: str | None) -> str | None:
        if method is None:
            return None
        upper_method = method.upper()
        if upper_method == "GET":
            return "query"
        if upper_method in {"POST", "PUT", "PATCH", "DELETE"}:
            return "command"
        return None

    def _extract_path(self, config: dict[str, object]) -> str | None:
        path = self._as_str(config.get("path"))
        if path:
            return path
        url = self._as_str(config.get("url"))
        if not url:
            return None
        marker = "://"
        if marker in url:
            _, remainder = url.split(marker, 1)
            slash_index = remainder.find("/")
            if slash_index >= 0:
                return remainder[slash_index:]
        return url
