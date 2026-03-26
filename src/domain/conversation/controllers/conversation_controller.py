from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from domain.conversation.schemas.conversation import ConversationRequest
from domain.execution.schemas.execution import Channel
from exceptions.service_exceptions import RouterValidationException
from services.conversation_boundary import ConversationBoundary
from utils.auth import AuthContext, get_auth_context


class ConversationController:
    def __init__(self, boundary: ConversationBoundary) -> None:
        self.boundary = boundary
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["conversations"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        self.router.add_api_route(
            "/conversations",
            self.send_message,
            methods=["POST"],
            response_class=EventSourceResponse,
            status_code=status.HTTP_200_OK,
        )

    async def send_message(
        self,
        request: Request,
        payload: ConversationRequest,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> AsyncGenerator[ServerSentEvent, None]:
        if idempotency_key is None:
            raise RouterValidationException(errors=["missing_idempotency_key"])
        parsed_last_event_id: int | None = None
        if last_event_id_header is not None:
            try:
                parsed_last_event_id = int(last_event_id_header)
            except ValueError as exc:
                raise RouterValidationException(
                    errors=["invalid_last_event_id"]
                ) from exc
            if parsed_last_event_id < 0:
                raise RouterValidationException(errors=["invalid_last_event_id"])

        trace_id_header: str = request.headers.get("X-Trace-Id")
        if trace_id_header:
            try:
                trace_uuid = UUID(trace_id_header)
            except ValueError:
                trace_uuid = (
                    UUID(hex=trace_id_header) if len(trace_id_header) == 32 else uuid4()
                )
        else:
            trace_uuid = uuid4()

        stream = await self.boundary.send_message(
            auth=auth,
            request=payload,
            channel=Channel.HTTP,
            headers=dict(request.headers),
            external_message_id=request.headers.get("X-External-Message-Id"),
            request_id=request.headers.get("X-Request-Id") or idempotency_key,
            trace_id=str(trace_uuid),
            last_event_id=parsed_last_event_id,
        )
        try:
            async for event in stream:
                yield event

        except asyncio.CancelledError:
            pass
