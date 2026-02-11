from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from domain.governance.repositories.rate_limit_policy_repository import (
    RateLimitPolicyRepository,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import (
    RateLimitExceededException,
    AuthorizationDeniedException,
)


class RateLimitService:
    def __init__(
        self,
        repository: RateLimitPolicyRepository,
        redis_adapter: RedisAdapter,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.repository = repository
        self.redis = redis_adapter
        self.tracer = tracer

    async def enforce(
        self,
        *,
        tenant_id: UUID,
        principal_type: str,
        principal_id: str,
        action: str,
    ) -> None:
        with self.tracer.observe(
            as_type="guardrail",
            name="governance.rate_limit.enforce",
            input={
                "tenant_id": str(tenant_id),
                "action": action,
                "principal_type": principal_type,
            },
            metadata={"guardrail_type": "rate_limit"},
        ) as enforce_handle:
            policy = await self.repository.get_default_policy_for_tenant(tenant_id)
            if enforce_handle:
                enforce_handle.success(
                    output={"policy": policy.to_dict() if policy else None}
                )

        if policy is None:
            with self.tracer.observe(
                as_type="event",
                name="governance.rate_limit.policy_missing",
                input={"tenant_id": str(tenant_id), "action": action},
            ) as event_handle:
                if event_handle:
                    event_handle.success(output={"reason": "policy_not_configured"})
            raise AuthorizationDeniedException(
                message="rate_limit_policy_not_configured"
            )

        version = await self.repository.get_published_policy_version(
            policy.rate_limit_policy_id,
            action=action,
            principal_type=principal_type,
        )
        if version is None:
            with self.tracer.observe(
                as_type="event",
                name="governance.rate_limit.policy_unpublished",
                input={
                    "policy_id": str(policy.rate_limit_policy_id),
                    "action": action,
                },
            ) as event_handle:
                if event_handle:
                    event_handle.success(output={"reason": "policy_not_published"})
            raise AuthorizationDeniedException(
                message="rate_limit_policy_not_published"
            )
        key = f"rate:{tenant_id}:{principal_type}:{principal_id}:{action}"

        with self.tracer.observe(
            as_type="tool",
            name="governance.rate_limit.increment",
            input={
                "tenant_id": str(tenant_id),
                "action": action,
                "principal_type": principal_type,
                "principal_id": principal_id,
                "key": key,
                "window_seconds": int(version.window_seconds),
            },
            metadata={"tool_name": "redis.incr_with_ttl"},
        ) as tool_handle:
            value = await self.redis.incr_with_ttl(key, int(version.window_seconds))
            if tool_handle:
                tool_handle.success(
                    output={
                        "count": int(value),
                        "window_seconds": int(version.window_seconds),
                    }
                )
        if int(value) > int(version.limit):
            with self.tracer.observe(
                as_type="event",
                name="governance.rate_limit.exceeded",
                input={
                    "tenant_id": str(tenant_id),
                    "action": action,
                    "principal_type": principal_type,
                    "principal_id": principal_id,
                    "limit": int(version.limit),
                    "count": int(value),
                },
            ) as event_handle:
                if event_handle:
                    event_handle.success(
                        output={
                            "exceeded": True,
                            "principal_type": principal_type,
                            "principal_id": principal_id,
                            "limit": int(version.limit),
                            "count": int(value),
                        }
                    )
            raise RateLimitExceededException(message="rate_limit_exceeded")
