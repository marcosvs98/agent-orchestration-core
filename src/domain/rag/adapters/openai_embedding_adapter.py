from __future__ import annotations

import asyncio
import hashlib
from typing import List

import settings
from openai import AsyncOpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse, Usage

from adapters.cache.redis_adapter import RedisAdapter
from adapters.observability.logging import get_logger
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.ports.embedding import EmbeddingPort

logger = get_logger()

EMBEDDING_CACHE_TTL_SECONDS = 86400


class OpenAIEmbeddingAdapter(EmbeddingPort):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = dimension
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    @staticmethod
    def _normalize_text_for_cache(text: str) -> str:
        return " ".join(text.strip().split())

    def _embedding_cache_key(self, text: str, model_name: str, dims: int) -> str:
        normalized = self._normalize_text_for_cache(text)
        h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"embedding:{model_name}:{dims}:{h}"

    def _embedding_batch_cache_key(
        self, texts: List[str], model_name: str, dims: int
    ) -> str:
        normalized_parts = [self._normalize_text_for_cache(t) for t in texts]
        payload = "\n".join(normalized_parts)
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"embedding_batch:{model_name}:{dims}:{h}"

    async def generate_embedding(
        self, text: str, *, model: str | None = None, dimension: int | None = None
    ) -> List[float]:
        model_name = model or self.model
        dims = dimension or self.dimension
        cache_key = self._embedding_cache_key(text, model_name, dims)
        if cached := await self.cache_adapter.get(cache_key):
            return list(cached["e"])

        with self.tracer.observe(
            as_type="embedding",
            name="domain.rag.adapters.openai_embedding_adapter.generate_embedding",
            input={"model": model_name, "dimension": dims},
        ) as embedding_handle:
            response = await self._request_with_retry(
                model=model_name,
                input_payload=text,
                dimensions=dims,
            )
            if not response.data:
                raise ValueError("embedding_response_empty")
            embedding = response.data[0].embedding
            usage: Usage = response.usage
            if not isinstance(embedding, list):
                raise ValueError("embedding_shape_invalid")
            if any(not isinstance(value, (int, float)) for value in embedding):
                raise ValueError("embedding_values_invalid")
            if len(embedding) != int(dims):
                raise ValueError("embedding_dimension_mismatch")
            if embedding_handle:
                embedding_handle.update(
                    output={"embedding_dimension": len(embedding)},
                    usage_details={
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.total_tokens - usage.prompt_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                )
            await self.cache_adapter.set(
                cache_key,
                {"e": embedding},
                ttl=EMBEDDING_CACHE_TTL_SECONDS,
            )
            return embedding

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        *,
        model: str | None = None,
        dimension: int | None = None,
    ) -> List[List[float]]:
        model_name = model or self.model
        dims = dimension or self.dimension
        cache_key = self._embedding_batch_cache_key(texts, model_name, dims)
        if cached := await self.cache_adapter.get(cache_key):
            return [list(emb) for emb in cached["e"]]

        with self.tracer.observe(
            as_type="embedding",
            name="domain.rag.adapters.openai_embedding_adapter.generate_embeddings_batch",
            input={
                "model": model_name,
                "dimension": dims,
                "batch_size": len(texts),
            },
        ) as embedding_handle:
            response = await self._request_with_retry(
                model=model_name,
                input_payload=texts,
                dimensions=dims,
            )
            embeddings = [item.embedding for item in response.data]
            if len(embeddings) != len(texts):
                raise ValueError("embedding_batch_size_mismatch")
            for embedding in embeddings:
                if not isinstance(embedding, list):
                    raise ValueError("embedding_shape_invalid")
                if any(not isinstance(value, (int, float)) for value in embedding):
                    raise ValueError("embedding_values_invalid")
                if len(embedding) != int(dims):
                    raise ValueError("embedding_dimension_mismatch")
            usage: Usage = response.usage
            if embedding_handle:
                embedding_handle.update(
                    output={
                        "embedding_count": len(embeddings),
                        "embedding_dimension": dims,
                    },
                    usage_details={
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.total_tokens - usage.prompt_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                )

            await self.cache_adapter.set(
                cache_key,
                {"e": embeddings},
                ttl=EMBEDDING_CACHE_TTL_SECONDS,
            )
            return embeddings

    async def _request_with_retry(
        self,
        *,
        model: str,
        input_payload: str | List[str],
        dimensions: int,
    ) -> CreateEmbeddingResponse:
        max_retries = max(0, int(settings.EMBEDDING_MAX_RETRIES))
        timeout_seconds = max(1, int(settings.EMBEDDING_REQUEST_TIMEOUT_SECONDS))
        base_delay = max(1, int(settings.EMBEDDING_RETRY_BASE_DELAY_MS)) / 1000
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.client.embeddings.create(
                        model=model,
                        input=input_payload,
                        dimensions=dimensions,
                    ),
                    timeout=timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                await asyncio.sleep(base_delay * (2**attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError("embedding_request_failed")
