from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from adapters.mcp.conversation_mcp_context import (
    _CONVERSATION_MCP_CONFIG,
    set_conversation_mcp_config,
)
from domain.conversation.schemas.conversation import ConversationRequest
from domain.conversation.services.mcp_config_loader import McpConfigLoader
from domain.execution.schemas.execution import Channel
from exceptions.service_exceptions import RouterValidationException
from services.conversation_boundary import ConversationBoundary
from utils.auth import AuthContext, get_auth_context_or_api_key

SAFE_CONVERSATION_HEADERS = {
    "x-request-id",
    "x-correlation-id",
    "idempotency-key",
    "x-trace-id",
    "x-external-message-id",
}

END_USER_AUTHORIZATION_HEADER = "X-End-User-Authorization"


class ConversationController:
    def __init__(self, boundary: ConversationBoundary, mcp_config_loader: McpConfigLoader) -> None:
        self.boundary = boundary
        self.mcp_config_loader = mcp_config_loader
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["conversations"],
            dependencies=[Depends(get_auth_context_or_api_key)],
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
        auth: AuthContext = Depends(get_auth_context_or_api_key),
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
                raise RouterValidationException(errors=["invalid_last_event_id"]) from exc
            if parsed_last_event_id < 0:
                raise RouterValidationException(errors=["invalid_last_event_id"])

        trace_id_header: str = request.headers.get("X-Trace-Id")
        if trace_id_header:
            try:
                trace_uuid = UUID(trace_id_header)
            except ValueError:
                trace_uuid = uuid4()
        else:
            trace_uuid = uuid4()

        mcp_config = await self.mcp_config_loader.load_for_tenant(tenant_id=auth.tenant_id)
        tok = set_conversation_mcp_config(mcp_config)
        try:
            stream = await self.boundary.send_message(
                auth=auth,
                request=payload,
                channel=Channel.HTTP,
                headers={
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() in SAFE_CONVERSATION_HEADERS
                },
                external_message_id=request.headers.get("X-External-Message-Id"),
                request_id=request.headers.get("X-Request-Id") or idempotency_key,
                trace_id=str(trace_uuid),
                last_event_id=parsed_last_event_id,
                end_user_authorization=_resolve_end_user_authorization(auth, request),
            )
            async for event in stream:
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)


def _resolve_end_user_authorization(auth: AuthContext, request: Request) -> str | None:
    if auth.principal_type in {"human", "user"}:
        return request.headers.get("Authorization")
    return request.headers.get(END_USER_AUTHORIZATION_HEADER)
