from __future__ import annotations

from domain.tools.services.openapi_parser import OpenAPIParser


def test_build_merged_request_schema_get_with_optional_query_month() -> None:
    parser = OpenAPIParser()
    operation = {
        "operationId": "spending_by_category",
        "parameters": [
            {
                "name": "month",
                "in": "query",
                "required": False,
                "description": "YYYY-MM; map natural-language months to this field.",
                "schema": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "title": "Month",
                },
            }
        ],
    }
    merged = parser.build_merged_request_schema(operation, {})
    assert merged["type"] == "object"
    assert merged["additionalProperties"] is False
    assert "month" in merged["properties"]
    assert merged["properties"]["month"]["type"] == "string"
    assert (
        merged["properties"]["month"]["description"]
        == "YYYY-MM; map natural-language months to this field."
    )
    assert merged["required"] == []


def test_build_merged_request_schema_path_query_and_json_body_merge() -> None:
    parser = OpenAPIParser()
    component_schemas = {
        "CreatePayload": {
            "type": "object",
            "properties": {"amount_minor": {"type": "integer"}},
            "required": ["amount_minor"],
        }
    }
    operation = {
        "operationId": "mixed",
        "parameters": [
            {
                "name": "client_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            },
            {
                "name": "verbose",
                "in": "query",
                "required": False,
                "schema": {"type": "boolean"},
            },
        ],
        "requestBody": {
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/CreatePayload"}}
            }
        },
    }
    merged = parser.build_merged_request_schema(operation, component_schemas)
    assert set(merged["properties"].keys()) == {"amount_minor", "client_id", "verbose"}
    assert "amount_minor" in merged["required"]
    assert "client_id" in merged["required"]
    assert "verbose" not in merged["required"]
