import copy
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

        for path_key, path_item in paths.items():
            if type(path_item) is not dict:
                continue
            for method in ["get", "post", "put", "patch", "delete"]:
                operation = path_item.get(method)
                if not operation:
                    continue
                if type(operation) is not dict:
                    continue

                request_schema = self.build_merged_request_schema(operation, schemas)
                response_schema = self.extract_success_json_response_schema(
                    operation, schemas
                )

                operations.append(
                    OpenAPIOperation(
                        path=path_key,
                        method=method.upper(),
                        operation_id=operation.get("operationId", f"{method}_{path_key}"),
                        summary=operation.get("summary"),
                        description=operation.get("description"),
                        examples=self.extract_request_body_examples(operation),
                        request_schema=request_schema,
                        response_schema=response_schema,
                    )
                )
        return operations

    def extract_request_body_examples(self, operation: dict[str, Any]) -> list[str]:
        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})
        json_content = content.get("application/json") or content.get(
            "application/json; charset=utf-8"
        )
        if not json_content:
            return []

        examples = json_content.get("examples")
        if type(examples) is not dict:
            return []

        extracted: list[str] = []
        for value in examples.values():
            if type(value) is not dict:
                continue
            example_value = value.get("value")
            if example_value is None:
                continue
            extracted.append(json.dumps(example_value, ensure_ascii=True))
        return extracted

    def build_merged_request_schema(
        self,
        operation: dict[str, Any],
        component_schemas: dict[str, Any],
    ) -> dict[str, Any]:
        merged_property_schemas: dict[str, Any] = {}
        merged_required_names: list[str] = []

        body_properties, body_required_names = self.extract_json_body_object_shape(
            operation, component_schemas
        )
        for property_name, property_schema in body_properties.items():
            merged_property_schemas[property_name] = copy.deepcopy(property_schema)
        for required_name in body_required_names:
            if required_name in merged_property_schemas:
                if required_name not in merged_required_names:
                    merged_required_names.append(required_name)

        parameters_list = operation.get("parameters") or []
        path_parameters_ordered: list[dict[str, Any]] = []
        query_parameters_ordered: list[dict[str, Any]] = []
        if type(parameters_list) is list:
            for parameter_entry in parameters_list:
                if type(parameter_entry) is not dict:
                    continue
                location = parameter_entry.get("in")
                if location == "path":
                    path_parameters_ordered.append(parameter_entry)
                elif location == "query":
                    query_parameters_ordered.append(parameter_entry)

        for parameter_entry in path_parameters_ordered + query_parameters_ordered:
            parameter_name = parameter_entry.get("name")
            if not parameter_name or type(parameter_name) is not str:
                continue
            raw_parameter_schema = parameter_entry.get("schema")
            if type(raw_parameter_schema) is not dict:
                raw_parameter_schema = {"type": "string"}
            normalized_schema = self.normalize_parameter_json_schema(
                raw_parameter_schema, component_schemas
            )
            prop_schema = copy.deepcopy(normalized_schema)
            param_desc = parameter_entry.get("description")
            if type(param_desc) is str and param_desc.strip():
                existing = prop_schema.get("description")
                if type(existing) is str and existing.strip():
                    prop_schema["description"] = (
                        f"{existing.strip()} {param_desc.strip()}".strip()
                    )
                else:
                    prop_schema["description"] = param_desc.strip()
            merged_property_schemas[parameter_name] = prop_schema
            if parameter_entry.get("required") is True:
                if parameter_name not in merged_required_names:
                    merged_required_names.append(parameter_name)

        if not merged_property_schemas:
            return {}

        return self.deep_resolve_refs(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": merged_property_schemas,
                "required": merged_required_names,
            },
            component_schemas,
        )

    def extract_json_body_object_shape(
        self,
        operation: dict[str, Any],
        component_schemas: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        request_body = operation.get("requestBody", {})
        if not request_body:
            return {}, []
        content = request_body.get("content", {})
        if not content:
            return {}, []
        json_content = content.get("application/json") or content.get(
            "application/json; charset=utf-8"
        )
        if not json_content:
            return {}, []
        schema_node = json_content.get("schema", {})
        if type(schema_node) is not dict:
            return {}, []
        dereferenced = self.dereference_schema_node(schema_node, component_schemas)
        properties_block = dereferenced.get("properties")
        if type(properties_block) is not dict:
            return {}, []
        required_block = dereferenced.get("required")
        required_names: list[str] = []
        if type(required_block) is list:
            for entry in required_block:
                required_names.append(str(entry))
        filtered_required = [
            name for name in required_names if name in properties_block
        ]
        return properties_block, filtered_required

    def dereference_schema_node(
        self,
        schema_node: dict[str, Any],
        component_schemas: dict[str, Any],
    ) -> dict[str, Any]:
        current: dict[str, Any] = schema_node
        guard = 0
        while "$ref" in current and guard < 32:
            guard += 1
            ref_path = current["$ref"]
            if type(ref_path) is not str:
                return current
            ref_key = ref_path.replace("#/components/schemas/", "")
            next_node = component_schemas.get(ref_key, {})
            if type(next_node) is not dict:
                return current
            current = next_node
        return current

    def deep_resolve_refs(
        self,
        node: Any,
        component_schemas: dict[str, Any],
        _depth: int = 0,
    ) -> Any:
        """Recursively inline all ``$ref`` so the schema is self-contained."""
        if _depth > 32 or not isinstance(node, dict):
            return node
        resolved = self.dereference_schema_node(node, component_schemas)
        out: dict[str, Any] = {}
        for k, v in resolved.items():
            if k == "properties" and isinstance(v, dict):
                out[k] = {
                    pn: self.deep_resolve_refs(ps, component_schemas, _depth + 1)
                    for pn, ps in v.items()
                }
            elif k == "items" and isinstance(v, dict):
                out[k] = self.deep_resolve_refs(v, component_schemas, _depth + 1)
            elif k in ("anyOf", "oneOf", "allOf") and isinstance(v, list):
                out[k] = [
                    self.deep_resolve_refs(item, component_schemas, _depth + 1)
                    if isinstance(item, dict)
                    else item
                    for item in v
                ]
            else:
                out[k] = v
        return out

    def normalize_parameter_json_schema(
        self,
        schema_fragment: dict[str, Any],
        component_schemas: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = self.deep_resolve_refs(schema_fragment, component_schemas)
        if "anyOf" in resolved:
            branches = resolved.get("anyOf")
            if type(branches) is list:
                for branch in branches:
                    if type(branch) is not dict:
                        continue
                    if branch.get("type") == "null":
                        continue
                    return {
                        key: value
                        for key, value in branch.items()
                        if key not in ("title", "default", "examples")
                    }
            return {"type": "string"}
        return {
            key: value
            for key, value in resolved.items()
            if key not in ("title", "default", "examples")
        }

    def extract_success_json_response_schema(
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

        if type(schema_ref) is not dict:
            return {}

        if "$ref" in schema_ref:
            ref_path = schema_ref["$ref"].replace("#/components/schemas/", "")
            resolved = schemas.get(ref_path, {})
            return resolved if type(resolved) is dict else {}

        return schema_ref
