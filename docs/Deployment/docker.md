# Deployment

## Containers

Build and run using the project `Dockerfile` / `docker-compose` definitions when present. Typical dependencies:

- **Postgres** with required extensions (for example `pgvector` where RAG is enabled)
- **Redis** for caches, rate limiting, or queues depending on configuration

## Health

Expose standard HTTP health endpoints as implemented in `rest.py` or the ASGI app factory.

## Scaling

Scale stateless API workers horizontally. Ensure shared databases and Redis are sized for connection counts and workload.
