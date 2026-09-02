from __future__ import annotations

import settings
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter


async def build_temporal_client() -> Client:
    return await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
        tls=settings.TEMPORAL_TLS,
        api_key=settings.TEMPORAL_API_KEY or None,
    )
