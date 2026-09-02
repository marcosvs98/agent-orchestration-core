from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Final, Tuple
from uuid import UUID

import structlog

from settings import OTEL_ATTRIBUTE_MAX_LENGTH

AttributeValue = (
    str
    | bool
    | int
    | float
    | Tuple[str, ...]
    | Tuple[bool, ...]
    | Tuple[int, ...]
    | Tuple[float, ...]
)

OBSERVATION_TYPE: Final[str] = "aoc.observation.type"
OBSERVATION_LEVEL: Final[str] = "aoc.observation.level"
OBSERVATION_INPUT: Final[str] = "aoc.observation.input"
OBSERVATION_OUTPUT: Final[str] = "aoc.observation.output"
OBSERVATION_VERSION: Final[str] = "aoc.observation.version"

GEN_AI_OPERATION_NAME: Final[str] = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME: Final[str] = "gen_ai.provider.name"
GEN_AI_REQUEST_MODEL: Final[str] = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL: Final[str] = "gen_ai.response.model"
GEN_AI_RESPONSE_FINISH_REASONS: Final[str] = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS: Final[str] = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: Final[str] = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_TOTAL_TOKENS: Final[str] = "gen_ai.usage.total_tokens"
GEN_AI_USAGE_CACHED_INPUT_TOKENS: Final[str] = "aoc.gen_ai.usage.cached_input_tokens"
GEN_AI_COST_USD: Final[str] = "aoc.gen_ai.cost.usd"
GEN_AI_INPUT_MESSAGES: Final[str] = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES: Final[str] = "gen_ai.output.messages"

EXCEPTION_TYPE: Final[str] = "exception.type"
EXCEPTION_MESSAGE: Final[str] = "exception.message"

HTTP_REQUEST_METHOD: Final[str] = "http.request.method"
HTTP_ROUTE: Final[str] = "http.route"
HTTP_RESPONSE_STATUS_CODE: Final[str] = "http.response.status_code"
HTTP_STATUS_CLASS: Final[str] = "aoc.http.status_class"
NETWORK_PROTOCOL_VERSION: Final[str] = "network.protocol.version"
USER_AGENT_ORIGINAL: Final[str] = "user_agent.original"

TENANT_ID: Final[str] = "tenant_id"
CORRELATION_ID: Final[str] = "correlation_id"
TRACE_ID: Final[str] = "trace_id"

CONTEXT_ATTRIBUTE_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "correlation_id",
        "request_id",
        "trace_id",
        "tenant_id",
        "request.method",
        "request.url.path",
    }
)

MODEL_PARAMETER_ATTRIBUTES: Final[Dict[str, str]] = {
    "temperature": "gen_ai.request.temperature",
    "max_tokens": "gen_ai.request.max_tokens",
    "max_output_tokens": "gen_ai.request.max_tokens",
    "top_p": "gen_ai.request.top_p",
    "top_k": "gen_ai.request.top_k",
    "frequency_penalty": "gen_ai.request.frequency_penalty",
    "presence_penalty": "gen_ai.request.presence_penalty",
    "seed": "gen_ai.request.seed",
    "stop": "gen_ai.request.stop_sequences",
}

INPUT_TOKEN_KEYS: Final[Tuple[str, ...]] = ("prompt_tokens", "input_tokens")
OUTPUT_TOKEN_KEYS: Final[Tuple[str, ...]] = ("completion_tokens", "output_tokens")
TOTAL_TOKEN_KEYS: Final[Tuple[str, ...]] = ("total_tokens",)
CACHED_INPUT_TOKEN_KEYS: Final[Tuple[str, ...]] = ("cached_input_tokens", "cache_read_input_tokens")
COST_KEYS: Final[Tuple[str, ...]] = ("total_cost", "cost_usd", "total_cost_usd")

_SCALAR_TYPES: Final[Tuple[type, ...]] = (str, bool, int, float)


def truncate(value: str) -> str:
    if len(value) <= OTEL_ATTRIBUTE_MAX_LENGTH:
        return value
    return value[: OTEL_ATTRIBUTE_MAX_LENGTH - 3] + "..."


def json_attribute(value: Any) -> str | None:
    if value is None:
        return None
    try:
        encoded = json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        encoded = str(value)
    return truncate(encoded)


def _sequence_attribute(value: Sequence[Any]) -> AttributeValue | None:
    items = list(value)
    if not items:
        return None
    first = items[0]
    for scalar_type in (bool, int, float, str):
        if isinstance(first, scalar_type) and all(isinstance(item, scalar_type) for item in items):
            if scalar_type is str:
                return tuple(truncate(item) for item in items)
            return tuple(items)
    return json_attribute(items)


def to_attribute_value(value: Any) -> AttributeValue | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return truncate(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return to_attribute_value(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set, frozenset)):
        return _sequence_attribute(list(value))
    if isinstance(value, Mapping):
        return json_attribute(dict(value))
    return truncate(str(value))


def sanitize_attributes(source: Mapping[str, Any] | None) -> Dict[str, AttributeValue]:
    if not source:
        return {}
    attributes: Dict[str, AttributeValue] = {}
    for key, raw in source.items():
        if not isinstance(key, str) or not key:
            continue
        converted = to_attribute_value(raw)
        if converted is None:
            continue
        attributes[key] = converted
    return attributes


def context_attributes() -> Dict[str, AttributeValue]:
    try:
        bound = structlog.contextvars.get_contextvars()
    except Exception:
        return {}
    allowed = {key: value for key, value in bound.items() if key in CONTEXT_ATTRIBUTE_ALLOWLIST}
    return sanitize_attributes(allowed)


def _first_int(source: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    for key in keys:
        raw = source.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            return raw
        if isinstance(raw, (float, Decimal)):
            return int(raw)
        if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            return int(raw.strip())
    return None


def _first_float(source: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        raw = source.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float, Decimal)):
            return float(raw)
        if isinstance(raw, str):
            try:
                return float(raw.strip())
            except ValueError:
                continue
    return None


def usage_attributes(usage_details: Any) -> Dict[str, AttributeValue]:
    if not isinstance(usage_details, Mapping):
        return {}
    attributes: Dict[str, AttributeValue] = {}
    input_tokens = _first_int(usage_details, INPUT_TOKEN_KEYS)
    if input_tokens is not None:
        attributes[GEN_AI_USAGE_INPUT_TOKENS] = input_tokens
    output_tokens = _first_int(usage_details, OUTPUT_TOKEN_KEYS)
    if output_tokens is not None:
        attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = output_tokens
    total_tokens = _first_int(usage_details, TOTAL_TOKEN_KEYS)
    if total_tokens is not None:
        attributes[GEN_AI_USAGE_TOTAL_TOKENS] = total_tokens
    cached_tokens = _first_int(usage_details, CACHED_INPUT_TOKEN_KEYS)
    if cached_tokens is not None:
        attributes[GEN_AI_USAGE_CACHED_INPUT_TOKENS] = cached_tokens
    return attributes


def cost_attributes(cost_details: Any) -> Dict[str, AttributeValue]:
    if not isinstance(cost_details, Mapping):
        return {}
    total_cost = _first_float(cost_details, COST_KEYS)
    if total_cost is None:
        return {}
    return {GEN_AI_COST_USD: total_cost}


def model_parameter_attributes(model_parameters: Any) -> Dict[str, AttributeValue]:
    if not isinstance(model_parameters, Mapping):
        return {}
    attributes: Dict[str, AttributeValue] = {}
    for key, raw in model_parameters.items():
        mapped = MODEL_PARAMETER_ATTRIBUTES.get(key)
        if mapped is None:
            continue
        converted = to_attribute_value(raw)
        if converted is not None:
            attributes[mapped] = converted
    return attributes
