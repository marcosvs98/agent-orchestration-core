from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

from domain.common.schemas.change import ChangeRequest
from domain.llm.schemas.llm import LLMProviderType
from domain.rag.schemas.embedding_job import EmbeddingStatus

SUPPORTED_EMBEDDING_DIMENSIONS: tuple[int, ...] = (512, 1024, 1536)
DEFAULT_EMBEDDING_DIMENSION: int = 1536
EMBEDDING_DIMENSION_REDUCED: int = 512


class VectorStore(BaseModel):
    """Represent an available vector store entry."""

    id: UUID
    name: str | None = None


class VectorStoreCreate(BaseModel):
    name: str


class RagCorpusKind(StrEnum):
    TENANT_KNOWLEDGE = "TENANT_KNOWLEDGE"
    USER_MEMORY = "USER_MEMORY"
    TOOL_CATALOG = "TOOL_CATALOG"


class RagChunkingStrategy(StrEnum):
    TOKEN_WINDOW = "TOKEN_WINDOW"
    RECURSIVE_CHARACTER = "RECURSIVE_CHARACTER"
    SEMANTIC = "SEMANTIC"
    PER_PAGE = "PER_PAGE"


class RagEmbeddingModelAlias(StrEnum):
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"


class RagNoContextBehavior(StrEnum):
    FALLBACK_MESSAGE = "FALLBACK_MESSAGE"


class RagUserMemoryDocumentType(StrEnum):
    USER_MEMORY_ITEM = "USER_MEMORY_ITEM"


class RagEmbeddingOptions(BaseModel):
    """Define embedding provider and model defaults for RAG."""

    provider: LLMProviderType = LLMProviderType.OPENAI
    model_alias: RagEmbeddingModelAlias = RagEmbeddingModelAlias.TEXT_EMBEDDING_3_SMALL
    dimension: Literal[512, 1024, 1536] = 1536
    model_id: UUID | None = None


class TokenWindowChunkingParams(BaseModel):
    strategy: Literal["TOKEN_WINDOW"] = "TOKEN_WINDOW"
    target_tokens: int = 500
    overlap_tokens: int = 50
    max_chunks_per_document: int = 100
    max_document_chars: int = 100_000


class RecursiveCharacterChunkingParams(BaseModel):
    strategy: Literal["RECURSIVE_CHARACTER"] = "RECURSIVE_CHARACTER"
    chunk_size: int = 2000
    chunk_overlap: int = 200
    max_chunks_per_document: int = 100
    max_document_chars: int = 100_000
    separators: list[str] = Field(
        default_factory=lambda: ["\n\n", "\n", " ", ""],
    )


class SemanticChunkingParams(BaseModel):
    strategy: Literal["SEMANTIC"] = "SEMANTIC"
    target_tokens: int = 500
    overlap_tokens: int = 50
    max_chunks_per_document: int = 100
    max_document_chars: int = 100_000


class PerPageChunkingParams(BaseModel):
    strategy: Literal["PER_PAGE"] = "PER_PAGE"
    max_document_chars: int = 100_000
    max_chunks_per_document: int = 500
    pages: list[str] = Field(default_factory=list)


RagChunkingRuleParams = Annotated[
    Union[
        TokenWindowChunkingParams,
        RecursiveCharacterChunkingParams,
        SemanticChunkingParams,
        PerPageChunkingParams,
    ],
    Field(discriminator="strategy"),
]


def parse_rag_chunking_rule_params(
    raw: object,
) -> (
    TokenWindowChunkingParams
    | RecursiveCharacterChunkingParams
    | SemanticChunkingParams
    | PerPageChunkingParams
):
    return TypeAdapter(RagChunkingRuleParams).validate_python(raw)


class RagRetrievalOptions(BaseModel):
    """Define retrieval limits and filters for similarity search."""

    top_k: int = 5
    similarity_threshold: float = 0.50
    filters: dict[str, object] | None = None


class RagGenerationContract(BaseModel):
    """Define how generation should behave when context is insufficient."""

    allow_extrapolation: bool = False
    no_context_behavior: RagNoContextBehavior = RagNoContextBehavior.FALLBACK_MESSAGE


class RagConfigOptions(BaseModel):
    """Define the full RAG options contract."""

    embedding: RagEmbeddingOptions = RagEmbeddingOptions()
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
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"


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
    metadata: dict[str, str | int | None]
    rag_config_id: UUID | None = None
    pages: list[str] | None = None


class RagDocumentsIngestBatchStatus(StrEnum):
    """Accepted batch ingestion status values."""

    ACCEPTED = "ACCEPTED"


class RagDocumentsIngestBatchAccepted(BaseModel):
    """Represent an accepted batch ingestion request for RAG documents."""

    rag_config_id: UUID
    job_id: UUID
    accepted_count: int
    status: RagDocumentsIngestBatchStatus = RagDocumentsIngestBatchStatus.ACCEPTED


class RagDocument(BaseModel):
    """Represent a document stored in the RAG repository."""

    id: UUID
    source: str | None = None
    doc_type: str | None = None
    content_hash: str
    metadata: dict[str, object] | None = None
    embedding_status: EmbeddingStatus | None = None
    rag_config_id: UUID | None = None


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
    chunking_rule_id: UUID
    corpus_kind: RagCorpusKind = RagCorpusKind.TENANT_KNOWLEDGE
    options: dict[str, object] | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None


class RagConfigCreate(BaseModel):
    """Define the payload to create a RAG configuration."""

    vector_store_id: UUID
    chunking_rule_id: UUID
    corpus_kind: RagCorpusKind = RagCorpusKind.TENANT_KNOWLEDGE
    options: dict[str, object] | None = None
    source_version_id: UUID | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None


class RagChunkingRuleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class RagChunkingRule(BaseModel):
    id: UUID
    name: str
    status: str
    strategy: str
    params: dict[str, object]
    config_hash: str | None = None


class RagChunkingRuleCreate(BaseModel):
    name: str
    status: RagChunkingRuleStatus = RagChunkingRuleStatus.ACTIVE
    strategy: RagChunkingStrategy
    params: dict[str, object]


class RagChunkingRuleUpdate(BaseModel):
    name: str | None = None
    status: RagChunkingRuleStatus | None = None
    strategy: RagChunkingStrategy | None = None
    params: dict[str, object] | None = None


class RagChunkingRuleUpdateHttpBody(BaseModel):
    change: ChangeRequest
    rule: RagChunkingRuleUpdate


class RagRetrievalPreviewRequest(BaseModel):
    rag_config_id: UUID
    user_input: str
    filters_override: dict[str, object] | None = None
    top_k_override: int | None = None
