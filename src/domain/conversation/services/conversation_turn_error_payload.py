from __future__ import annotations
from exceptions.service_exceptions import DomainValidationException


class ConversationTurnErrorPayload:
    @staticmethod
    def structured_error(
        *,
        exc: Exception,
        model: str,
        has_mcp_tools: bool,
        has_message_history: bool,
        trace_metadata: dict[str, str | int | bool | None] | None = None,
    ) -> dict[str, object]:
        if isinstance(exc, DomainValidationException):
            error_code = exc.message or "domain_validation_error"
            provider_errors = [str(item) for item in exc.errors()]
        else:
            error_code = type(exc).__name__
            provider_errors = [type(exc).__name__]
        payload_preview: dict[str, object] = {
            "has_mcp_tools": has_mcp_tools,
            "has_message_history": has_message_history,
        }
        if model:
            payload_preview["model"] = model
        if trace_metadata:
            for key in (
                "prompt_layer_count",
                "history_strategy",
                "history_message_count",
                "has_selected_prompt",
                "has_rag_context",
            ):
                if key in trace_metadata:
                    payload_preview[key] = trace_metadata[key]
        return {
            "message": error_code,
            "code": error_code,
            "details": {
                "type": type(exc).__name__,
                "provider_errors": provider_errors,
                "payload_preview": payload_preview,
            },
        }

    @staticmethod
    def sse_error(
        *,
        error_code: str,
        correlation_id: str,
        trace_id: str | None,
        interaction_id: str | None,
    ) -> dict[str, str | None]:
        payload: dict[str, str | None] = {
            "code": "conversation_turn_failed",
            "message": "conversation_turn_failed",
            "error_code": error_code,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
        }
        if interaction_id is not None:
            payload["debug_id"] = interaction_id
        return payload
