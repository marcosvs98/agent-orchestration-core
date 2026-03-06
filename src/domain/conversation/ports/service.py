from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Protocol
from uuid import UUID

from fastapi.sse import ServerSentEvent

from domain.conversation.schemas.conversation import ConversationRequest
from domain.execution.schemas.execution import Channel


class ConversationServicePort(Protocol):
    async def execute_turn(
        self,
        *,
        tenant_id: UUID,
        request: ConversationRequest,
        channel: Channel,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
        last_event_id: int | None,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        ...
