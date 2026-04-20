# Communication patterns

This service exposes **HTTP APIs** (FastAPI) for orchestration and management. Internal modules communicate through **domain services** and **repository** interfaces; cross-cutting observability uses the **tracer port** (Langfuse adapter).

For a full system view, see [Architecture/ARCHITECTURE.md](Architecture/ARCHITECTURE.md).
