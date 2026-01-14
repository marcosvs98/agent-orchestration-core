from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from domain.governance.repositories.rate_limit_policy_repository import RateLimitPolicyRepository
from exceptions.service_exceptions import RateLimitExceededException, AuthorizationDeniedException


class RateLimitService:
    def __init__(self, repository: RateLimitPolicyRepository, redis_adapter: RedisAdapter) -> None:
        self.repository = repository
        self.redis = redis_adapter

    async def enforce(
        self,
        *,
        tenant_id: UUID,
        principal_type: str,
        principal_id: str,
        action: str,
    ) -> None:
        policy = await self.repository.get_default_policy_for_tenant(tenant_id)
        if policy is None:
            raise AuthorizationDeniedException(message="rate_limit_policy_not_configured")
        version = await self.repository.get_published_policy_version(
            policy.rate_limit_policy_id, action=action, principal_type=principal_type
        )
        if version is None:
            raise AuthorizationDeniedException(message="rate_limit_policy_not_published")

        key = f"rate:{tenant_id}:{principal_type}:{principal_id}:{action}"
        value = await self.redis.incr_with_ttl(key, int(version.window_seconds))
        if int(value) > int(version.limit):
            raise RateLimitExceededException(message="rate_limit_exceeded")
