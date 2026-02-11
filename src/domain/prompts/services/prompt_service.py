from __future__ import annotations

import hashlib
import time
from typing import Optional
from uuid import UUID

import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError

from adapters.observability.logging import get_logger
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.observability.event_payloads import (
    NodePromptUpdatedPayload,
)
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate
from exceptions.service_exceptions import DomainValidationException

logger = get_logger()


class PromptCacheEntry:
    def __init__(self, prompt: NodePrompt, timestamp: float, ttl: int = 3600):
        self.prompt = prompt
        self.timestamp = timestamp
        self.ttl = ttl

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class PromptService:
    def __init__(
        self,
        tracer: RuntimeTracerPort,
        repository: PromptRepository,
        execution_repository: ExecutionRepository | None = None,
        cache_ttl: int = 3600,
    ) -> None:
        self.repository = repository
        self.execution_repository = execution_repository
        self.cache_ttl = cache_ttl
        self.tracer = tracer
        self._cache: dict[str, PromptCacheEntry] = {}

    @staticmethod
    def _calculate_frozen_hash(template_text: str) -> str:
        return hashlib.sha256(template_text.encode()).hexdigest()

    def _invalidate_cache(self, node_type: str) -> None:
        if node_type in self._cache:
            del self._cache[node_type]

    def _validate_schema(self, schema_id: str | None, schema_data: dict | None) -> bool:
        if schema_id is None or schema_data is None:
            return True
        try:
            jsonschema.Draft202012Validator.check_schema(schema_data)
            return True
        except JsonSchemaValidationError as exc:
            logger.warning(
                "Invalid JSON schema",
                schema_id=schema_id,
                error=str(exc),
            )
            return False

    def _validate_prompt(self, prompt: NodePrompt) -> bool:
        if not prompt.template_text or len(prompt.template_text.strip()) == 0:
            return False

        if prompt.input_schema_id:
            try:
                schema_data = self._load_schema(prompt.input_schema_id)
                if schema_data and not self._validate_schema(
                    prompt.input_schema_id, schema_data
                ):
                    return False
            except Exception as exc:
                logger.warning(
                    "Failed to load input schema",
                    schema_id=prompt.input_schema_id,
                    error=str(exc),
                )

        if prompt.output_schema_id:
            try:
                schema_data = self._load_schema(prompt.output_schema_id)
                if schema_data and not self._validate_schema(
                    prompt.output_schema_id, schema_data
                ):
                    return False
            except Exception as exc:
                logger.warning(
                    "Failed to load output schema",
                    schema_id=prompt.output_schema_id,
                    error=str(exc),
                )

        return True

    def _load_schema(self, schema_id: str) -> dict:
        return {}

    async def get_prompt(self, node_type: str) -> Optional[NodePrompt]:
        entry = self._cache.get(node_type)
        if entry and not entry.is_expired():
            return entry.prompt

        prompt = await self.repository.get_active_prompt(node_type)
        if prompt:
            self._cache[node_type] = PromptCacheEntry(
                prompt, time.time(), self.cache_ttl
            )
        return prompt

    async def create_or_update_prompt(
        self, create: NodePromptCreate, tenant_id: UUID | None = None
    ) -> NodePrompt:
        with self.tracer.observe(
            as_type="agent",
            name="domain.prompts.prompt_service.create_or_update_prompt",
            input={"node_type": create.node_type},
        ):
            frozen_hash = self._calculate_frozen_hash(create.template_text)

            existing = await self.repository.get_active_prompt(create.node_type)
            if existing:
                from domain.prompts.schemas.prompt import NodePromptUpdate

                update_data = NodePromptUpdate(
                    template_text=create.template_text,
                    input_schema_id=create.input_schema_id,
                    output_schema_id=create.output_schema_id,
                    description=create.description,
                )
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.prompts.prompt_service.update_prompt",
                    input={"prompt_id": str(existing.prompt_id)},
                ):
                    prompt = await self.repository.update_prompt(
                        existing.prompt_id, update_data, frozen_hash
                    )
            else:
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.prompts.prompt_service.create_prompt",
                    input={"node_type": create.node_type},
                ):
                    prompt = await self.repository.create_prompt(create, frozen_hash)

            if not self._validate_prompt(prompt):
                raise DomainValidationException(
                    message="prompt_validation_failed",
                    detail="Prompt validation failed",
                )

            self._invalidate_cache(create.node_type)

            if self.execution_repository and tenant_id:
                payload: NodePromptUpdatedPayload = NodePromptUpdatedPayload(
                    prompt_id=str(prompt.prompt_id),
                    node_type=prompt.node_type,
                    version=prompt.version,
                    frozen_hash=prompt.frozen_hash,
                    created_by=prompt.created_by or "system",
                )
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.prompts.prompt_service.append_execution_event",
                    input={"prompt_id": str(prompt.prompt_id)},
                ):
                    await self.execution_repository.append_execution_event(
                        tenant_id=tenant_id,
                        session_id=None,
                        flow_run_id=None,
                        event_type=ExecutionEventType.NodePromptUpdated,
                        payload=payload,
                        correlation_id=None,
                        causation_id=None,
                        schema_version=1,
                        node_id=None,
                        edge_id=None,
                    )

            logger.info(
                "Prompt created or updated",
                node_type=prompt.node_type,
                version=prompt.version,
                frozen_hash=prompt.frozen_hash,
            )

            return prompt

    async def deactivate_prompt(
        self, node_type: str, tenant_id: UUID | None = None
    ) -> None:
        prompt = await self.repository.get_active_prompt(node_type)
        if prompt:
            with self.tracer.observe(
                as_type="tool",
                name="domain.prompts.prompt_service.deactivate_prompt",
                input={"prompt_id": str(prompt.prompt_id)},
            ):
                await self.repository.deactivate_prompt(prompt.prompt_id)
            self._invalidate_cache(node_type)
            logger.info("Prompt deactivated", node_type=node_type)
