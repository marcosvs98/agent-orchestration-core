from __future__ import annotations

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.prompts.node_prompt import NodePrompt

from seeds.demo.ids import (
    PRINCIPAL_SYSTEM,
    PROMPT_CLARIFICATION_ID,
    PROMPT_INTENT_ID,
    PROMPT_RESPONSE_ID,
    PROMPT_SLOT_ID,
    PROMPT_TOOL_SELECTION_ID,
)


def _calculate_frozen_hash(template_text: str) -> str:
    return hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:64]


async def seed_prompts() -> None:
    async with get_db() as session:
        intent_template = """# Task
Classify all user intents types and confidence."""

        slot_template = """# Task
Extract parameters from user input to fill the request schema.
You can use context from the previous conversation to complete slots.

# Selected Tools
{{ ctx.derived.selected_tools | tojson }}

# Constraints
- Do not invent values.
"""
        clarification_template = """# Task
Ask the user for missing required information.

# Intent
{{ ctx.input.input_payload.intent | default('') }}

# Constraints
- Be concise and polite.
- Ask only for missing fields.
- Do not reference schemas or system internals.
"""

        response_template = """# Task
{% if ctx.tool_response %}
If tool_response is present and non-empty: format it as a natural language message for the user in one concise sentence.
{% endif %}
If tool_response is empty or absent: the user asked an informative question (e.g. how to do something). Answer using the retrieved context and user_input; be short and helpful.
You can use context from the previous conversation to complete slots.

{% if ctx.input.input_payload.original_intent %}
# Intent
{{ ctx.input.input_payload.original_intent }}
{% endif %}

{% if ctx.tool_response %}
# Tool Response
{{ ctx.tool_response | tojson }}
{% endif %}

# Output Guidelines
{% if ctx.tool_response %}
- When tool_response is present: generate only one concise sentence; use product-oriented language; do not list fields or bullets; if success is true, confirm the expense was registered.
{% endif %}
- When tool_response is empty: answer the user question using the provided context; be concise.
- Do not mention status codes, endpoints, requests, or payloads."""

        tool_selection_template = """# Task
Select the best matching tool(s) for each user intent. Return one entry per intent type when the user has multiple intents.

# Available tools
{{ ctx.meta.available_tools | tojson }}

# Constraints
- selected_tool must reference a tool from available_tools by name and tool_config_id.
- confidence between 0 and 1.
"""

        prompts = [
            (
                PROMPT_INTENT_ID,
                "IntentDetectionNode",
                intent_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "intent_type": {
                                        "type": "string",
                                        "enum": [
                                            "query",
                                            "execution",
                                            "generation",
                                            "transformation",
                                            "conversation",
                                        ],
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "minimum": 0,
                                        "maximum": 1,
                                    },
                                    "priority": {"type": "integer", "minimum": 1},
                                },
                                "required": ["intent_type", "confidence", "priority"],
                            },
                        },
                        "overall_confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "required": [
                        "result",
                        "overall_confidence",
                    ],
                },
            ),
            (
                PROMPT_SLOT_ID,
                "ParamExtractionNode",
                slot_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "operation_id": {"type": "string"},
                                    "tool_name": {"type": "string"},
                                    "status": {
                                        "type": "string",
                                        "enum": ["ready", "incomplete"],
                                    },
                                    "params": {
                                        "type": "object",
                                    },
                                    "missing_fields": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "field": {"type": "string"},
                                                "reason": {"type": "string"},
                                            },
                                            "required": ["field", "reason"],
                                        },
                                    },
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "blocking": {"type": "boolean"},
                                },
                                "required": [
                                    "operation_id",
                                    "tool_name",
                                    "status",
                                    "params",
                                    "missing_fields",
                                    "depends_on",
                                    "blocking",
                                ],
                            },
                        },
                    },
                    "required": ["result"],
                },
            ),
            (
                PROMPT_CLARIFICATION_ID,
                "ClarificationNode",
                clarification_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "system_output": {"type": "string"},
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "operation_id": {"type": "string"},
                                    "tool_name": {"type": "string"},
                                    "missing_fields": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "field": {"type": "string"},
                                                "reason": {"type": "string"},
                                            },
                                            "required": ["field", "reason"],
                                        },
                                    },
                                },
                                "required": [
                                    "operation_id",
                                    "tool_name",
                                    "missing_fields",
                                ],
                            },
                        },
                    },
                    "required": ["system_output", "result"],
                },
            ),
            (
                PROMPT_RESPONSE_ID,
                "ResponseComposer",
                response_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "system_output": {"type": "string"},
                        "operations_summary": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "operation_id": {"type": "string"},
                                    "status": {"type": "string"},
                                },
                                "required": ["operation_id", "status"],
                            },
                        },
                        "turn_status": {
                            "type": "string",
                            "enum": [
                                "completed",
                                "partial_success",
                                "clarification_required",
                                "escalated",
                                "failed",
                            ],
                        },
                    },
                    "required": [
                        "system_output",
                        "operations_summary",
                        "turn_status",
                    ],
                },
            ),
            (
                PROMPT_TOOL_SELECTION_ID,
                "ToolSelectionNode",
                tool_selection_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "intent_type": {
                                        "type": "string",
                                        "enum": [
                                            "query",
                                            "execution",
                                            "generation",
                                            "transformation",
                                            "conversation",
                                        ],
                                    },
                                    "selected_tool": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "tool_config_id": {"type": "string"},
                                        },
                                        "required": ["name", "tool_config_id"],
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "minimum": 0,
                                        "maximum": 1,
                                    },
                                },
                                "required": [
                                    "intent_type",
                                    "selected_tool",
                                    "confidence",
                                ],
                            },
                        },
                    },
                    "required": ["result"],
                },
            ),
        ]

        for prompt_id, node_type, template_text, output_schema in prompts:
            result = await session.execute(
                select(NodePrompt).where(
                    NodePrompt.prompt_id == prompt_id
                )
            )
            existing = result.scalar_one_or_none()
            frozen_hash = _calculate_frozen_hash(template_text)

            if existing is None:
                prompt = NodePrompt(
                    prompt_id=prompt_id,
                    node_type=node_type,
                    template_text=template_text,
                    output_schema=output_schema,
                    version=1,
                    frozen_hash=frozen_hash,
                    is_active=True,
                    description=f"Prompt for {node_type}",
                    created_by=PRINCIPAL_SYSTEM,
                )
                session.add(prompt)
            else:
                existing.node_type = node_type
                existing.template_text = template_text
                existing.output_schema = output_schema
                existing.version = max(int(existing.version or 1), 1)
                existing.frozen_hash = frozen_hash
                existing.is_active = True
                existing.description = f"Prompt for {node_type}"
                existing.created_by = PRINCIPAL_SYSTEM
                session.add(existing)

        await session.commit()
