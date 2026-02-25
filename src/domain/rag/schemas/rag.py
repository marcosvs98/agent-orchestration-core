from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel
from domain.rag.schemas.embedding_job import EmbeddingStatus


class VectorStore(BaseModel):
    """Represent an available vector store entry."""

    id: UUID
    name: str | None = None


class RagEmbeddingOptions(BaseModel):
    """Define embedding provider and model defaults for RAG."""

    provider: str = "OPENAI"
    model_alias: str = "text-embedding-3-small"
    dimension: int = 1536


class RagChunkingOptions(BaseModel):
    """Define chunking limits and overlap for ingestion."""

    target_tokens: int = 500
    overlap_tokens: int = 50
    max_chunks_per_document: int = 100
    max_document_chars: int = 100000


class RagRetrievalOptions(BaseModel):
    """Define retrieval limits and filters for similarity search."""

    top_k: int = 5
    similarity_threshold: float = 0.50
    filters: dict[str, object] | None = None


class RagGenerationContract(BaseModel):
    """Define how generation should behave when context is insufficient."""

    allow_extrapolation: bool = False
    no_context_behavior: str = "FALLBACK_MESSAGE"


class RagConfigOptions(BaseModel):
    """Define the full RAG options contract."""

    embedding: RagEmbeddingOptions = RagEmbeddingOptions()
    chunking: RagChunkingOptions = RagChunkingOptions()
    retrieval: RagRetrievalOptions = RagRetrievalOptions()
    generation_contract: RagGenerationContract = RagGenerationContract()


class RagContextItem(BaseModel):
    """Represent a retrieved context item used for generation."""

    document_id: UUID
    chunk_id: UUID
    content: str
    score: float
    metadata: dict[str, object] | None = None
    created_at: datetime | None = None
    observed_at: datetime | None = None


class RagContextReason(StrEnum):
    OK = "OK"
    NO_MATCHES = "NO_MATCHES"


class RagContext(BaseModel):
    """Represent the retrieval outcome used by the generator."""

    context_items: list[RagContextItem]
    context_summary: str | None = None
    eligible: bool
    reason: RagContextReason
    generation_contract: RagGenerationContract | None = None


class RagDocumentCreate(BaseModel):
    """Define the payload to ingest a document into the RAG store."""

    source: str
    doc_type: str
    content: str
    version: str | None = None
    metadata: dict[str, object] | None = None


class RagDocument(BaseModel):
    """Represent a document stored in the RAG repository."""

    id: UUID
    source: str | None = None
    doc_type: str | None = None
    content_hash: str
    metadata: dict[str, object] | None = None
    embedding_status: EmbeddingStatus | None = None


class RagPreparedDocument(BaseModel):
    id: UUID
    source: str | None = None
    doc_type: str | None = None
    content_hash: str
    metadata: dict[str, object] | None = None
    embedding_status: EmbeddingStatus = EmbeddingStatus.PENDING


class RagChunk(BaseModel):
    """Represent a chunk stored in the RAG repository."""

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    score: float | None = None
    metadata: dict[str, object] | None = None


class RagConfig(BaseModel):
    """Represent a RAG configuration instance."""

    id: UUID
    vector_store_id: UUID
    options: dict[str, object] | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None


class RagConfigCreate(BaseModel):
    """Define the payload to create a RAG configuration."""

    vector_store_id: UUID
    options: dict[str, object] | None = None
    source_version_id: UUID | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
