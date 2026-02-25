'''
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
        try:
            prompt_output_schema.get
        except AttributeError:
            return {}

        with self.tracer.observe(
            as_type="chain",
            name="domain.llm.structured_output_schema_composer.compose_for_slot_filling",
            input={
                "flow_run_id": str(execution_context.flow_run_id),
                "current_node_id": execution_context.current_node_id,
            },
        ):
            tool_config_id = self._extract_tool_config_id(execution_context)
            if tool_config_id is None:
                return deepcopy(prompt_output_schema)

            request_schema = await self._get_request_schema(tool_config_id)
            if not request_schema:
                return deepcopy(prompt_output_schema)

            composed = deepcopy(prompt_output_schema)
            result_items_schema = self._get_result_items_schema(composed)
            if not result_items_schema:
                return composed

            result_items_properties = self._get_mapping(result_items_schema.get("properties"))
            if not result_items_properties:
                return composed

            result_items_properties["params"] = self._build_params_schema(request_schema)
            result_items_schema["properties"] = result_items_properties
            result_items_schema["required"] = list(result_items_properties.keys())
            result_items_schema["additionalProperties"] = False

            missing_fields_schema = self._get_mapping(result_items_properties.get("missing_fields"))
            missing_fields_items = self._get_mapping(missing_fields_schema.get("items"))
            missing_fields_properties = self._get_mapping(missing_fields_items.get("properties"))
            if missing_fields_properties:
                missing_fields_items["required"] = list(missing_fields_properties.keys())
                missing_fields_items["additionalProperties"] = False
                missing_fields_schema["items"] = missing_fields_items
                result_items_properties["missing_fields"] = missing_fields_schema

            result_items_schema["properties"] = result_items_properties
            return composed

    def _extract_tool_config_id(self, execution_context: ExecutionContext) -> UUID | None:
        try:
            tool_selection = execution_context.get_node_output(NodeType.ToolSelectionNode)
            result = tool_selection.get("result") or []
            selected_tool = result[0].get("selected_tool") or {}
            tool_config_id = selected_tool.get("tool_config_id")
            if tool_config_id is None:
                return None
            return UUID(str(tool_config_id))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return None

    async def _get_request_schema(self, tool_config_id: UUID) -> dict[str, Any]:
        tool_config = await self.tools_repository.get_tool_config(tool_config_id)
        if tool_config is None:
            return {}
        config = self._get_mapping(tool_config.config)
        request_schema = self._get_mapping(config.get("request_schema"))
        if not request_schema:
            return {}
        return request_schema

    def _build_params_schema(self, request_schema: dict[str, Any]) -> dict[str, Any]:
        request_properties = self._get_mapping(request_schema.get("properties"))
        request_required = request_schema.get("required") or []
        required_fields: list[str] = []
        for field in request_required:
            try:
                request_properties[field]
            except (KeyError, TypeError):
                continue
            required_fields.append(field)

        params_properties: dict[str, Any] = {}
        for field in required_fields:
            field_schema = self._get_mapping(request_properties.get(field))
            if not field_schema:
                continue
            params_properties[field] = deepcopy(field_schema)

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": params_properties,
            "required": list(params_properties.keys()),
        }

    def _get_result_items_schema(self, output_schema: dict[str, Any]) -> dict[str, Any]:
        properties = self._get_mapping(output_schema.get("properties"))
        result_schema = self._get_mapping(properties.get("result"))
        return self._get_mapping(result_schema.get("items"))

    @staticmethod
    def _get_mapping(value: Any) -> dict[str, Any]:
        try:
            value.get
        except AttributeError:
            return {}
        return value'''


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
            tool_config_id = self._extract_tool_config_id(execution_context)
            if not tool_config_id:
                return deepcopy(prompt_output_schema)

            request_schema = await self._get_request_schema(tool_config_id)
            if not request_schema:
                return deepcopy(prompt_output_schema)

            composed = deepcopy(prompt_output_schema)
            result_items_schema = self._get_result_items_schema(composed)
            if not result_items_schema:
                return composed

            result_properties = self._get_mapping(result_items_schema.get("properties"))
            if not result_properties:
                return composed

            result_properties["params"] = self._build_params_schema(request_schema)
            self._update_object_schema(result_properties["params"])

            missing_fields_items = self._get_mapping(
                result_properties.get("missing_fields", {}).get("items")
            )
            if missing_fields_items:
                self._update_object_schema(missing_fields_items)
                result_properties["missing_fields"]["items"] = missing_fields_items

            result_items_schema["properties"] = result_properties
            self._update_object_schema(result_items_schema)

            return composed

    def _extract_tool_config_id(self, execution_context: ExecutionContext) -> UUID | None:
        try:
            tool_selection = execution_context.get_node_output(NodeType.ToolSelectionNode) or {}
            selected_tool = next(iter(tool_selection.get("result", [{}])), {}).get("selected_tool") or {}
            tool_config_id = selected_tool.get("tool_config_id")
            return UUID(str(tool_config_id)) if tool_config_id else None
        except (AttributeError, TypeError, ValueError):
            return None

    async def _get_request_schema(self, tool_config_id: UUID) -> dict[str, Any]:
        tool_config = await self.tools_repository.get_tool_config(tool_config_id)
        if not tool_config:
            return {}
        config = self._get_mapping(tool_config.config)
        return self._get_mapping(config.get("request_schema"))

    def _build_params_schema(self, request_schema: dict[str, Any]) -> dict[str, Any]:
        request_properties = self._get_mapping(request_schema.get("properties"))
        params_properties = {
            field: deepcopy(request_properties[field])
            for field in request_schema.get("required", [])
            if field in request_properties
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": params_properties,
            "required": list(params_properties.keys()),
        }

    def _get_result_items_schema(self, output_schema: dict[str, Any]) -> dict[str, Any]:
        return self._get_mapping(
            self._get_mapping(
                self._get_mapping(output_schema.get("properties")).get("result")
            ).get("items")
        )

    @staticmethod
    def _get_mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _update_object_schema(schema: dict[str, Any]) -> None:
        props = schema.get("properties")
        if isinstance(props, dict) and props:
            schema["required"] = list(props.keys())
            schema["additionalProperties"] = False