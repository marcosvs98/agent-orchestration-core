from __future__ import annotations

from unittest.mock import AsyncMock

from domain.llm.services.structured_output_schema_composer import (
    StructuredOutputSchemaComposer,
)


class FakeTracer:
    def observe(self, **kwargs):
        class CM:
            def __enter__(self):
                return None

            def __exit__(self, *args):
                return False

        return CM()


def test_build_strict_slot_params_schema_empty_request_is_valid_strict_object() -> None:
    composer = StructuredOutputSchemaComposer(
        tools_repository=AsyncMock(),
        tracer=FakeTracer(),
    )
    out = composer.build_strict_slot_params_schema({})
    assert out == {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    }


def test_build_strict_slot_params_schema_optional_and_required_fields() -> None:
    composer = StructuredOutputSchemaComposer(
        tools_repository=AsyncMock(),
        tracer=FakeTracer(),
    )
    request_schema = {
        "type": "object",
        "properties": {
            "month": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["limit"],
    }
    out = composer.build_strict_slot_params_schema(request_schema)
    assert set(out["properties"].keys()) == {"limit", "month"}
    assert set(out["required"]) == {"limit", "month"}
    assert out["properties"]["limit"] == {"type": "integer"}
    assert out["properties"]["month"] == {
        "anyOf": [
            {"type": "string"},
            {"type": "null"},
        ],
    }
