# type: ignore
from decouple import config

ENVIRONMENT: str = config("ENVIRONMENT", default="development", cast=str)
APPLICATION_NAME: str = config("APPLICATION_NAME", default="agent-orchestration-core", cast=str)
APPLICATION_DESCRIPTION: str = config(
    "APPLICATION_DESCRIPTION", default="Agent Orchestration Core API"
)
APPLICATION_VERSION: str = config("APPLICATION_VERSION", default="1.0.0", cast=str)
HOST: str = config("HOST", default="0.0.0.0", cast=str)
PORT: int = config("PORT", default=8010, cast=int)
LOG_LEVEL: str = config("LOG_LEVEL", default="DEBUG", cast=str)
RELOAD: bool = config("RELOAD", default=False, cast=bool)
PYTEST_RUNNING: int = config("PYTEST_RUNNING", default=0, cast=int)
TRACING_ENABLE: bool = config("TRACING_ENABLE", default=False, cast=bool)

DATABASE_URL: str = config(
    "DATABASE_URL",
    default="postgresql+asyncpg://postgres:password@localhost:5432/agent_router",
    cast=str,
)

REDIS_HOST: str = config("REDIS_HOST", default="localhost")
REDIS_PASSWORD: str | None = config("REDIS_PASSWORD", default=None)
REDIS_PORT: int = config("REDIS_PORT", default=6379, cast=int)
REDIS_SSL: bool = config("REDIS_SSL", default=False, cast=bool)
REDIS_DB: int = config("REDIS_DB", default=0, cast=int)
REDIS_DEFAULT_TTL: int = config("REDIS_DEFAULT_TTL", default=3600, cast=int)
CACHE_SILENT_MODE: bool = config("CACHE_SILENT_MODE", default=True, cast=bool)
DEFAULT_TTL: int = config("DEFAULT_TTL", default=3600, cast=int)
TURN_WINDOW_TTL: int = config("TURN_WINDOW_TTL", default=7200, cast=int)
PERSONA_CACHE_TTL: int = config("PERSONA_CACHE_TTL", default=1800, cast=int)
DEDUP_TTL: int = config("DEDUP_TTL", default=86400, cast=int)
EMBEDDING_QUEUE_NAME: str = config(
    "EMBEDDING_QUEUE_NAME",
    default="process_embedding_job",
    cast=str,
)
EMBEDDING_QUEUE_MAX_ATTEMPTS: int = config(
    "EMBEDDING_QUEUE_MAX_ATTEMPTS",
    default=3,
    cast=int,
)
MAX_USER_MEMORY_DOCUMENTS: int = config(
    "MAX_USER_MEMORY_DOCUMENTS",
    default=10_000,
    cast=int,
)

OPENAI_API_KEY: str = config("OPENAI_API_KEY", default="", cast=str)
OPENAI_CONVERSATION_MODEL: str = config("OPENAI_CONVERSATION_MODEL", default="gpt-4.1", cast=str)
OPENAI_MODERATION_MODEL: str = config(
    "OPENAI_MODERATION_MODEL", default="omni-moderation-latest", cast=str
)
EMBEDDING_DIMENSION: int = config(
    "EMBEDDING_DIMENSION",
    default=1536,
    cast=int,
)
EMBEDDING_REQUEST_TIMEOUT_SECONDS: int = config(
    "EMBEDDING_REQUEST_TIMEOUT_SECONDS",
    default=15,
    cast=int,
)
EMBEDDING_MAX_RETRIES: int = config(
    "EMBEDDING_MAX_RETRIES",
    default=2,
    cast=int,
)
EMBEDDING_RETRY_BASE_DELAY_MS: int = config(
    "EMBEDDING_RETRY_BASE_DELAY_MS",
    default=200,
    cast=int,
)
EMBEDDING_FALLBACK_MODEL: str = config(
    "EMBEDDING_FALLBACK_MODEL",
    default="",
    cast=str,
)
SLM_MODEL_PATH: str = config(
    "SLM_MODEL_PATH", default="models/Qwen2.5-1.5B-Instruct-GGUF", cast=str
)
SLM_INFERENCE_TIMEOUT_MS: int = config("SLM_INFERENCE_TIMEOUT_MS", default=500, cast=int)
LLM_DEFAULT_MAX_LATENCY_MS: int = config("LLM_DEFAULT_MAX_LATENCY_MS", default=15000, cast=int)

LANGFUSE_PUBLIC_KEY: str | None = config("LANGFUSE_PUBLIC_KEY", default=None)
LANGFUSE_SECRET_KEY: str | None = config("LANGFUSE_SECRET_KEY", default=None)
LANGFUSE_HOST: str = config("LANGFUSE_HOST", default="https://cloud.langfuse.com", cast=str)
TRACING_ENABLED: bool = config("TRACING_ENABLED", default=True, cast=bool)
TRACING_LEVEL: str = config("TRACING_LEVEL", default="DEFAULT", cast=str)

OTEL_SERVICE_NAME: str = config("OTEL_SERVICE_NAME", default="agent-orchestration-core", cast=str)
OTEL_EXPORTER_OTLP_ENDPOINT: str = config(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317", cast=str
)

JWT_SECRET: str = config("JWT_SECRET", default="", cast=str)
JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256", cast=str)
JWT_ISSUER: str = config("JWT_ISSUER", default="", cast=str)
JWT_AUDIENCE: str = config("JWT_AUDIENCE", default="", cast=str)
JWT_LEEWAY_SECONDS: int = config("JWT_LEEWAY_SECONDS", default=0, cast=int)
JWT_TENANT_TOKEN_EXPIRES_SECONDS: int = config(
    "JWT_TENANT_TOKEN_EXPIRES_SECONDS", default=3600, cast=int
)
ADMIN_API_KEY: str = config("ADMIN_API_KEY", default="", cast=str)
PUBLIC_BASE_URL: str = config("PUBLIC_BASE_URL", default="", cast=str)
IDEMPOTENCY_TTL_SECONDS: int = config("IDEMPOTENCY_TTL_SECONDS", default=3600, cast=int)
RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED: bool = config(
    "RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED", default=True, cast=bool
)

USER_INPUT_COMPOSED_MAX_CHARS: int = config(
    "USER_INPUT_COMPOSED_MAX_CHARS",
    default=1_048_576,
    cast=int,
)
DOCUMENT_CONVERSION_TIMEOUT_SECONDS: int = config(
    "DOCUMENT_CONVERSION_TIMEOUT_SECONDS",
    default=120,
    cast=int,
)
DOCLING_ENABLED: bool = config("DOCLING_ENABLED", default=False, cast=bool)
