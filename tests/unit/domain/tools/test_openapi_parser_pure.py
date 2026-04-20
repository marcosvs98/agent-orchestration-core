from __future__ import annotations

from domain.tools.schemas.openapi_types import OpenAPISpec
from domain.tools.services.openapi_parser import OpenAPIParser


def test_extract_operations_skips_non_dict_path_items() -> None:
    p = OpenAPIParser()
    spec = OpenAPISpec(
        title="t",
        version="1",
        paths={"/x": "bad"},
        schemas={},
        openapi_version="3.0.0",
        servers=[],
        components={},
    )
    assert p.extract_operations(spec) == []


def test_extract_operations_collects_post() -> None:
    p = OpenAPIParser()
    spec = OpenAPISpec(
        title="t",
        version="1",
        paths={
            "/pets": {
                "post": {
                    "operationId": "createPet",
                    "summary": "Create",
                }
            }
        },
        schemas={},
        openapi_version="3.0.0",
        servers=[],
        components={},
    )
    ops = p.extract_operations(spec)
    assert len(ops) == 1
    assert ops[0]["method"] == "POST"
    assert ops[0]["path"] == "/pets"


def test_extract_request_body_examples_empty() -> None:
    p = OpenAPIParser()
    assert p.extract_request_body_examples({}) == []


def test_extract_request_body_examples_from_json_examples() -> None:
    p = OpenAPIParser()
    out = p.extract_request_body_examples(
        {
            "requestBody": {
                "content": {
                    "application/json": {
                        "examples": {
                            "a": {"value": {"k": 1}},
                        }
                    }
                }
            }
        }
    )
    assert out == ['{"k": 1}']
