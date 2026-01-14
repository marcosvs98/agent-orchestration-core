# type: ignore
from decouple import config

ENVIRONMENT: str = config("ENVIRONMENT", default="development", cast=str)
APPLICATION_NAME: str = config("APPLICATION_NAME", default="agent-orchestration-core", cast=str)
APPLICATION_VERSION: str = config("APPLICATION_VERSION", default="1.0.0", cast=str)
HOST: str = config("HOST", default="0.0.0.0", cast=str)
PORT: int = config("PORT", default=8010, cast=int)
LOG_LEVEL: str = config("LOG_LEVEL", default="DEBUG", cast=str)
RELOAD: bool = config("RELOAD", default=False, cast=bool)
PYTEST_RUNNING: int = config("PYTEST_RUNNING", default=0, cast=int)

DATABASE_URL: str = config(
    "DATABASE_URL",
    default="postgresql+asyncpg://postgres:password@localhost:5432/agent_router",
    cast=str,
)

REDIS_HOST: str = config("REDIS_HOST", default="localhost")
REDIS_PASSWORD: str | None = config("REDIS_PASSWORD", default=None)
REDIS_PORT: int = config("REDIS_PORT", default=6379, cast=int)
REDIS_SSL: bool = config("REDIS_SSL", default=False, cast=bool)
REDIS_DEFAULT_TTL: int = config("REDIS_DEFAULT_TTL", default=3600, cast=int)
CACHE_SILENT_MODE: bool = config("CACHE_SILENT_MODE", default=True, cast=bool)
DEFAULT_TTL: int = config("DEFAULT_TTL", default=3600, cast=int)
TURN_WINDOW_TTL: int = config("TURN_WINDOW_TTL", default=7200, cast=int)
PERSONA_CACHE_TTL: int = config("PERSONA_CACHE_TTL", default=1800, cast=int)
DEDUP_TTL: int = config("DEDUP_TTL", default=86400, cast=int)

OPENAI_API_KEY: str = config("OPENAI_API_KEY", default="", cast=str)

# OBSERVABILITY (Langfuse)
LANGFUSE_PUBLIC_KEY: str | None = config("LANGFUSE_PUBLIC_KEY", default=None)
LANGFUSE_SECRET_KEY: str | None = config("LANGFUSE_SECRET_KEY", default=None)
LANGFUSE_HOST: str = config(
    "LANGFUSE_HOST", default="https://cloud.langfuse.com", cast=str
)

# TRACING (OpenTelemetry)
OTEL_SERVICE_NAME: str = config(
    "OTEL_SERVICE_NAME", default="agent-orchestration-core", cast=str
)
OTEL_EXPORTER_OTLP_ENDPOINT: str = config(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317", cast=str
)

JWT_SECRET: str = config("JWT_SECRET", default="", cast=str)
JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256", cast=str)
JWT_ISSUER: str = config("JWT_ISSUER", default="", cast=str)
JWT_AUDIENCE: str = config("JWT_AUDIENCE", default="", cast=str)
JWT_LEEWAY_SECONDS: int = config("JWT_LEEWAY_SECONDS", default=0, cast=int)
IDEMPOTENCY_TTL_SECONDS: int = config("IDEMPOTENCY_TTL_SECONDS", default=3600, cast=int)