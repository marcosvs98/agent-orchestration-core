from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RagConfigPreviewRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    vector_store_id: UUID
    name: str
    rag_config_id: UUID
    status: str


class RagTenantSummaryData(BaseModel):
    model_config = ConfigDict(frozen=True)

    vector_stores_count: int
    documents_count: int
    chunks_count: int
    rag_configs_count: int
    configs: list[RagConfigPreviewRow] = Field(default_factory=list)
