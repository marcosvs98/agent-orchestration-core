from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel


class EmbeddingContract(BaseModel):
    provider: str = "openai"
    model: str
    dimension: int
    metric: str
    version: int

    @property
    def contract_hash(self) -> str:
        payload = f"{self.provider}|{self.model}|{self.dimension}|{self.metric}|{self.version}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EmbeddingExecutionRequest(BaseModel):
    text: str
    contract: EmbeddingContract
    use_case: Literal["indexing", "retrieval"]
    allow_fallback: bool = False


class EmbeddingBatchExecutionRequest(BaseModel):
    texts: list[str]
    contract: EmbeddingContract
    use_case: Literal["indexing", "retrieval"]


class EmbeddingProviderSelection(BaseModel):
    provider: str
    provider_model: str
    contract: EmbeddingContract
