from uuid import UUID

from pydantic import BaseModel


class VectorStore(BaseModel):
    id: UUID
    name: str | None = None


class RagConfig(BaseModel):
    id: UUID
    vector_store_id: UUID
    options: dict[str, object] | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None


class RagConfigCreate(BaseModel):
    vector_store_id: UUID
    options: dict[str, object] | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None