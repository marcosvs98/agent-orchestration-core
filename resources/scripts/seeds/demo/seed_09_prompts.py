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
    PROMPT_INPUT_MODERATION_ID,
    PROMPT_INTENT_ID,
    PROMPT_MEMORY_PAYLOAD_SUMMARIZE_ID,
    PROMPT_RESPONSE_ID,
    PROMPT_SLOT_ID,
    PROMPT_TOOL_SELECTION_ID,
    PROMPT_FALLBACK_SLA_ID,
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

# Today
{{ ctx.meta.current_date }}
Resolve relative dates against this date and emit them as YYYY-MM-DD.

# Selected Tools
{{ ctx.derived.selected_tools | tojson }}

# Constraints
- Use only names that appear in the request schema for `params` and for `missing_fields[].field`.
- When the user’s wording clearly matches a field, fill it in the format the schema expects; do not add values or entities they did not convey.
- `ready` when every required field in the schema is satisfied; otherwise `incomplete` and list only what is still missing.
"""
        clarification_template = """# Task
Ask the user for missing required information.

# Intent
{{ ctx.input.input_payload.intent | default('') }}

# Missing Fields
{{ ctx.derived.missing_fields | tojson }}

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
- When tool_response is present: generate only one concise sentence; use product-oriented language; do not list fields or bullets; if success is true, confirm the operation succeeded.
{% endif %}
- When tool_response is empty: answer the user question using the provided context; be concise.
- Do not mention status codes, endpoints, requests, or payloads."""

        tool_selection_template = """# Task
Select the best matching tool(s) for the user's intent. Return one entry per distinct intent.

# Available tools
{{ ctx.meta.available_tools | tojson }}

# Intent-to-method mapping
- When the user wants to CREATE, REGISTER, ADD, RECORD, or INSERT something new → prefer tools with method POST.
- When the user wants to LIST, VIEW, SHOW, SEARCH, or CONSULT existing data → prefer tools with method GET.
- Match the user's ACTION VERB to the correct HTTP method. Do NOT use a GET/list tool when the user clearly wants to create or register.

# Constraints
- selected_tool must reference a tool from available_tools by name and tool_config_id.
- confidence between 0 and 1.
- intent_type: "query" for GET tools, "command" for POST/PUT/PATCH/DELETE tools."""
        input_moderation_template = """You are a moderation classifier.
Return JSON only.
{
 "flagged": boolean
}

flagged = true if the text contains hate, harassment, sexual content,
self harm, violence, or offensive language."""

        memory_payload_summarize_template = """# Task
Compress the raw ToolInputFiller-related payload for durable user memory.

# Raw payload (JSON)
{{ ctx.input.input_payload.memory_payload_raw | tojson }}

# Rules
- Return only valid JSON matching the output schema.
- Preserve semantically important fields; drop noise.
- Do not add facts that are not supported by the raw payload."""

        fallback_template = """Classify the user message.

high = system error blocking usage
medium = insults, aggression, anger, legal threats
low = frustration, cancellation or normal question

Never downgrade priority.

Reply in English using this template:
"Your ticket is <ticket> and it will be resolved within <time>."

time:
high = 4 hours
medium = 8 hours
low = 24 hours

Return only JSON:

{
  "system_output": "...",
  "new_priority": "high | medium | low"
}"""
        prompts = [
            (
                PROMPT_INPUT_MODERATION_ID,
                "ContentModeration",
                input_moderation_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"flagged": {"type": "boolean"}},
                    "required": ["flagged"],
                },
            ),
            (
                PROMPT_FALLBACK_SLA_ID,
                "HumanFallback",
                fallback_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "system_output": {"type": "string"},
                        "new_priority": {"type": "string"},
                    },
                    "required": ["system_output", "new_priority"]
                }
            ),
            (
                PROMPT_INTENT_ID,
                "IntentClassifier",
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
                                            "command",
                                            "conversation",
                                            "update_user_preferences",
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
                "ToolInputFiller",
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
                                        "additionalProperties": False,
                                        "properties": {},
                                        "required": [],
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
                "QueryClarifier",
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
                "ResponseBuilder",
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
                PROMPT_MEMORY_PAYLOAD_SUMMARIZE_ID,
                "ContextSummarizer",
                memory_payload_summarize_template,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "prepared_memory_data": {"type": "object"},
                        "reason_code": {"type": "string"},
                    },
                    "required": ["prepared_memory_data"],
                },
            ),
            (
                PROMPT_TOOL_SELECTION_ID,
                "ToolResolver",
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
                                            "command",
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
