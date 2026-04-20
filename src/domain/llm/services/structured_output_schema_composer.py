from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.prompts.schemas.prompt import NodeType
from domain.tools.repositories.tools_repository import ToolsRepository


class StructuredOutputSchemaComposer:
    def __init__(
        self,
        tools_repository: ToolsRepository,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.tools_repository = tools_repository
        self.tracer = tracer

    async def compose_for_slot_filling(
        self,
        *,
        execution_context: ExecutionContext,
        prompt_output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(prompt_output_schema, dict):
            return {}

        with self.tracer.observe(
            as_type="chain",
            name="domain.llm.structured_output_schema_composer.compose_for_slot_filling",
            input={
                "flow_run_id": str(execution_context.flow_run_id),
                "current_node_id": execution_context.current_node_id,
            },
        ):
            tool_config_uuid = self.extract_tool_config_uuid_from_execution_context(
                execution_context
            )
            if tool_config_uuid is None:
                return deepcopy(prompt_output_schema)

            request_schema_from_tool = await self.load_request_schema_for_tool_config(
                tool_config_uuid
            )

            composed_output_schema = deepcopy(prompt_output_schema)
            slot_result_item_schema = self.extract_slot_filler_result_item_schema(
                composed_output_schema
            )
            if not slot_result_item_schema:
                return composed_output_schema

            result_top_properties = slot_result_item_schema.get("properties")
            if type(result_top_properties) is not dict:
                return composed_output_schema

            updated_result_properties = dict(result_top_properties)
            updated_result_properties["params"] = self.build_strict_slot_params_schema(
                request_schema_from_tool
            )

            missing_fields_container = updated_result_properties.get("missing_fields")
            if type(missing_fields_container) is dict:
                missing_field_item_schema = missing_fields_container.get("items")
                if type(missing_field_item_schema) is dict:
                    self.apply_strict_required_keys_to_object_schema(missing_field_item_schema)
                    updated_result_properties["missing_fields"] = {
                        **missing_fields_container,
                        "items": missing_field_item_schema,
                    }

            slot_result_item_schema["properties"] = updated_result_properties
            self.apply_strict_required_keys_to_object_schema(slot_result_item_schema)

            return composed_output_schema

    def extract_tool_config_uuid_from_execution_context(
        self, execution_context: ExecutionContext
    ) -> UUID | None:
        try:
            tool_selection = execution_context.get_node_output(NodeType.ToolResolver) or {}
            result_rows = tool_selection.get("result") or []
            if not result_rows:
                return None
            first_row = result_rows[0]
            if type(first_row) is not dict:
                return None
            selected_tool = first_row.get("selected_tool") or {}
            if type(selected_tool) is not dict:
                return None
            tool_config_id = selected_tool.get("tool_config_id")
            if not tool_config_id:
                return None
            return UUID(str(tool_config_id))
        except (AttributeError, TypeError, ValueError):
            return None

    async def load_request_schema_for_tool_config(self, tool_config_id: UUID) -> dict[str, Any]:
        tool_config = await self.tools_repository.get_tool_config(tool_config_id)
        if tool_config is None:
            return {}
        config_mapping = tool_config.config
        if type(config_mapping) is not dict:
            return {}
        request_schema = config_mapping.get("request_schema")
        if type(request_schema) is not dict:
            return {}
        return request_schema

    def build_strict_slot_params_schema(
        self, request_schema_from_openapi: dict[str, Any]
    ) -> dict[str, Any]:
        raw_properties = request_schema_from_openapi.get("properties")
        if type(raw_properties) is not dict:
            raw_properties = {}
        raw_required_list = request_schema_from_openapi.get("required")
        if type(raw_required_list) is not list:
            raw_required_list = []

        params_property_schemas: dict[str, Any] = {
            property_name: deepcopy(raw_properties[property_name])
            for property_name in sorted(raw_properties.keys())
        }
        openapi_required: set[str] = set()
        for candidate in raw_required_list:
            candidate_key = str(candidate)
            if candidate_key in params_property_schemas:
                openapi_required.add(candidate_key)

        # OpenAI structured outputs (strict): every key in `properties` must appear in
        # `required`. Optional OpenAPI params become required keys that may be JSON null.
        final_properties: dict[str, Any] = {}
        for property_name in sorted(params_property_schemas.keys()):
            prop_schema = deepcopy(params_property_schemas[property_name])
            if property_name in openapi_required:
                final_properties[property_name] = prop_schema
            else:
                final_properties[property_name] = self._optional_param_schema_allowing_null(
                    prop_schema
                )

        all_keys = sorted(final_properties.keys())

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": final_properties,
            "required": all_keys,
        }

    @staticmethod
    def _optional_param_schema_allowing_null(prop_schema: dict[str, Any]) -> dict[str, Any]:
        """Wrap schema so the model may output null for an OpenAPI-optional slot."""
        inner = deepcopy(prop_schema)
        return {
            "anyOf": [
                inner,
                {"type": "null"},
            ],
        }

    def extract_slot_filler_result_item_schema(
        self, output_schema_root: dict[str, Any]
    ) -> dict[str, Any] | None:
        root_properties = output_schema_root.get("properties")
        if type(root_properties) is not dict:
            return None
        result_array_schema = root_properties.get("result")
        if type(result_array_schema) is not dict:
            return None
        item_schema = result_array_schema.get("items")
        if type(item_schema) is not dict:
            return None
        return item_schema

    def apply_strict_required_keys_to_object_schema(self, object_schema: dict[str, Any]) -> None:
        properties_block = object_schema.get("properties")
        if type(properties_block) is not dict:
            return
        if not properties_block:
            return
        object_schema["required"] = list(properties_block.keys())
        object_schema["additionalProperties"] = False
