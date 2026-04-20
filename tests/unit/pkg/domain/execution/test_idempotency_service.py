from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.adapters.idempotency_service import IdempotencyService


class TestIdempotencyService:
    @pytest.fixture
    def redis_adapter(self):
        adapter = MagicMock()
        adapter.set_if_not_exists = AsyncMock()
        adapter.get = AsyncMock()
        adapter.set = AsyncMock()
        return adapter

    @pytest.fixture
    def tracer(self):
        return MagicMock()

    @pytest.fixture
    def service(self, redis_adapter, tracer):
        return IdempotencyService(redis_adapter, tracer)

    @pytest.mark.asyncio
    async def test_build_key_includes_tenant_endpoint_and_key(self, service):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "test-key-123"
        key = service.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        assert str(tenant_id) in key
        assert endpoint in key
        assert idempotency_key in key
        assert key.startswith("idempotency:")

    @pytest.mark.asyncio
    async def test_try_acquire_returns_true_when_key_not_exists(self, service, redis_adapter):
        redis_adapter.set_if_not_exists.return_value = True
        result = await service.try_acquire("test-key")
        assert result is True
        redis_adapter.set_if_not_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_acquire_returns_false_when_key_exists(self, service, redis_adapter):
        redis_adapter.set_if_not_exists.return_value = False
        result = await service.try_acquire("test-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_retrieves_value_from_redis(self, service, redis_adapter):
        expected = {"status": "PROCESSING"}
        redis_adapter.get.return_value = expected
        result = await service.get("test-key")
        assert result == expected
        redis_adapter.get.assert_called_once_with("test-key")

    @pytest.mark.asyncio
    async def test_get_returns_none_when_key_not_found(self, service, redis_adapter):
        redis_adapter.get.return_value = None
        result = await service.get("test-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_result_stores_data_with_ttl(self, service, redis_adapter):
        data = {"flow_run_id": "123", "response": {}}
        await service.set_result("test-key", data)
        redis_adapter.set.assert_called_once()
