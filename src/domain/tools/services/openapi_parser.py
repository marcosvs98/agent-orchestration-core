import json
from typing import Any

import httpx
import yaml

from domain.tools.schemas.openapi_types import OpenAPIOperation, OpenAPISpec
from exceptions.service_exceptions import DomainValidationException


class OpenAPIParser:
    async def parse_openapi_spec(self, openapi_url: str) -> OpenAPISpec:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(openapi_url)
                response.raise_for_status()
                content = response.text
        except httpx.HTTPError as e:
            raise DomainValidationException(
                message=f"failed_to_fetch_openapi_spec: {str(e)}"
            ) from e

        try:
            if content.strip().startswith("{"):
                spec_dict = json.loads(content)
            else:
                spec_dict = yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise DomainValidationException(
                message=f"invalid_openapi_format: {str(e)}"
            ) from e

        if not isinstance(spec_dict, dict):
            raise DomainValidationException(
                message="invalid_openapi_spec: root must be an object"
            )
        if "openapi" not in spec_dict and "swagger" not in spec_dict:
            raise DomainValidationException(
                message="invalid_openapi_spec: missing 'openapi' or 'swagger' version field"
            )
        paths = spec_dict.get("paths")
        if not isinstance(paths, dict):
            raise DomainValidationException(
                message="invalid_openapi_spec: missing or invalid 'paths' field"
            )

        info = spec_dict.get("info", {})
        title = info.get("title") or info.get("name")
        version = info.get("version")
        paths = spec_dict.get("paths", {})
        components = spec_dict.get("components", {})
        schemas = components.get("schemas", {})

        return OpenAPISpec(
            title=title,
            version=version,
            paths=paths,
            schemas=schemas,
            openapi_version=spec_dict.get("openapi") or spec_dict.get("swagger"),
            servers=spec_dict.get("servers", []),
            components=components,
        )

    def extract_operations(self, openapi_spec: OpenAPISpec) -> list[OpenAPIOperation]:
        operations = []
        paths = openapi_spec.get("paths", {})
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                operation = path_item.get(method)
                if not operation:
                    continue

                request_schema = self._extract_request_schema(operation, schemas)
                response_schema = self._extract_response_schema(operation, schemas)

                operations.append(
                    OpenAPIOperation(
                        path=path,
                        method=method.upper(),
                        operation_id=operation.get("operationId", f"{method}_{path}"),
                        request_schema=request_schema,
                        response_schema=response_schema,
                    )
                )
        return operations

    def _extract_request_schema(
        self, operation: dict[str, Any], schemas: dict[str, Any]
    ) -> dict[str, Any]:
        request_body = operation.get("requestBody", {})
        if not request_body:
            return {}

        content = request_body.get("content", {})
        if not content:
            return {}

        json_content = content.get("application/json") or content.get(
            "application/json; charset=utf-8"
        )
        if not json_content:
            return {}

        schema_ref = json_content.get("schema", {})
        if not schema_ref:
            return {}

        if "$ref" in schema_ref:
            ref_path = schema_ref["$ref"].replace("#/components/schemas/", "")
            return schemas.get(ref_path, {})

        return schema_ref

    def _extract_response_schema(
        self, operation: dict[str, Any], schemas: dict[str, Any]
    ) -> dict[str, Any]:
        responses = operation.get("responses", {})
        success_response = responses.get("200") or responses.get("201")
        if not success_response:
            return {}

        content = success_response.get("content", {})
        if not content:
            return {}

        json_content = content.get("application/json") or content.get(
            "application/json; charset=utf-8"
        )
        if not json_content:
            return {}

        schema_ref = json_content.get("schema", {})
        if not schema_ref:
            return {}

        if "$ref" in schema_ref:
            ref_path = schema_ref["$ref"].replace("#/components/schemas/", "")
            return schemas.get(ref_path, {})

        return schema_ref
