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
EXPOSE_API_DOCS: bool = config("EXPOSE_API_DOCS", default=ENVIRONMENT == "development", cast=bool)

DATABASE_URL: str = config(
    "DATABASE_URL",
    default="postgresql+asyncpg://postgres:password@localhost:5432/agent_router",
    cast=str,
)

REDIS_URL: str = config("REDIS_URL", default="", cast=str)
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

TRACING_ENABLED: bool = config("TRACING_ENABLED", default=True, cast=bool)
METRICS_ENABLED: bool = config("METRICS_ENABLED", default=True, cast=bool)
LOGS_ENABLED: bool = config("LOGS_ENABLED", default=True, cast=bool)

TOOL_IMPORT_DEFAULT_BASE_URL: str = config("TOOL_IMPORT_DEFAULT_BASE_URL", default="", cast=str)

OTEL_SERVICE_NAME: str = config("OTEL_SERVICE_NAME", default="agent-orchestration-core", cast=str)
OTEL_SERVICE_NAMESPACE: str = config(
    "OTEL_SERVICE_NAMESPACE", default="agent-orchestration", cast=str
)
OTEL_EXPORTER_OTLP_ENDPOINT: str = config(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4318", cast=str
)
OTEL_EXPORTER_OTLP_HEADERS: str = config("OTEL_EXPORTER_OTLP_HEADERS", default="", cast=str)
OTEL_CAPTURE_CONTENT: bool = config("OTEL_CAPTURE_CONTENT", default=False, cast=bool)
OTEL_ATTRIBUTE_MAX_LENGTH: int = config("OTEL_ATTRIBUTE_MAX_LENGTH", default=4096, cast=int)
OTEL_SAMPLE_RATIO_DEFAULT: float = config("OTEL_SAMPLE_RATIO_DEFAULT", default=1.0, cast=float)
OTEL_SAMPLE_RATIO_REPOSITORY: float = config(
    "OTEL_SAMPLE_RATIO_REPOSITORY", default=0.1, cast=float
)
OTEL_METRIC_EXPORT_INTERVAL_MS: int = config(
    "OTEL_METRIC_EXPORT_INTERVAL_MS", default=15000, cast=int
)
OTEL_FLUSH_TIMEOUT_MS: int = config("OTEL_FLUSH_TIMEOUT_MS", default=2000, cast=int)
OTEL_SHUTDOWN_TIMEOUT_MS: int = config("OTEL_SHUTDOWN_TIMEOUT_MS", default=10000, cast=int)

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

TEMPORAL_ENABLED: bool = config("TEMPORAL_ENABLED", default=False, cast=bool)
TEMPORAL_HOST: str = config("TEMPORAL_HOST", default="localhost:7233", cast=str)
TEMPORAL_NAMESPACE: str = config("TEMPORAL_NAMESPACE", default="default", cast=str)
TEMPORAL_TASK_QUEUE: str = config("TEMPORAL_TASK_QUEUE", default="flow-runs", cast=str)
TEMPORAL_TLS: bool = config("TEMPORAL_TLS", default=False, cast=bool)
TEMPORAL_API_KEY: str = config("TEMPORAL_API_KEY", default="", cast=str)
TEMPORAL_FAIRNESS_ENABLED: bool = config("TEMPORAL_FAIRNESS_ENABLED", default=False, cast=bool)
TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES: int = config(
    "TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES",
    default=20,
    cast=int,
)
TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS: int = config(
    "TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS",
    default=50,
    cast=int,
)
TEMPORAL_NODE_START_TO_CLOSE_TIMEOUT_MS: int = config(
    "TEMPORAL_NODE_START_TO_CLOSE_TIMEOUT_MS",
    default=30_000,
    cast=int,
)
TEMPORAL_WORKFLOW_RUN_TIMEOUT_MS: int = config(
    "TEMPORAL_WORKFLOW_RUN_TIMEOUT_MS",
    default=120_000,
    cast=int,
)
TEMPORAL_TURN_WAIT_TIMEOUT_MS: int = config(
    "TEMPORAL_TURN_WAIT_TIMEOUT_MS",
    default=125_000,
    cast=int,
)
TEMPORAL_TOOL_RUN_TASK_QUEUE: str = config(
    "TEMPORAL_TOOL_RUN_TASK_QUEUE",
    default="tool-runs",
    cast=str,
)
TEMPORAL_TOOL_RUN_MAX_ATTEMPTS: int = config(
    "TEMPORAL_TOOL_RUN_MAX_ATTEMPTS",
    default=3,
    cast=int,
)

FLOW_RUN_RECONCILER_ENABLED: bool = config(
    "FLOW_RUN_RECONCILER_ENABLED",
    default=True,
    cast=bool,
)
FLOW_RUN_RECONCILER_INTERVAL_SECONDS: int = config(
    "FLOW_RUN_RECONCILER_INTERVAL_SECONDS",
    default=60,
    cast=int,
)
FLOW_RUN_RECONCILER_STALE_AFTER_SECONDS: int = config(
    "FLOW_RUN_RECONCILER_STALE_AFTER_SECONDS",
    default=900,
    cast=int,
)
FLOW_RUN_RECONCILER_BATCH_SIZE: int = config(
    "FLOW_RUN_RECONCILER_BATCH_SIZE",
    default=50,
    cast=int,
)
