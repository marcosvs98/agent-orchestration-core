from __future__ import annotations

import hashlib
import json
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
)


def _calculate_frozen_hash(template_text: str) -> str:
    return hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:64]


async def seed_prompts() -> None:
    async with get_db() as session:
        intent_template = """# Task
Select exactly one tool that best matches the user input and classify the user intention.

# Intent categories
- TRANSACTION: The user is giving data or a clear instruction to execute the tool now (e.g. "Registrar 50 reais no mercado", "Criar despesa de 100").
- DECLARATION: The user is asking for information (how, what, whether), e.g. "Como registro uma despesa?", "Posso registrar despesa parcelada?", "O que preciso para registrar?".
- SMALL_TALK: Greetings, thanks, or off-topic.

Mentioning a topic does not imply execution. "Como registrar uma despesa?" is DECLARATION even if a createExpense tool exists.

# Input
User message: {ctx[user_input]}

Available tools:
{ctx[context][available_tools]}

# Output Format
Return a JSON object:
{{
  "intent": "tool_name_or_null",
  "tool_config_id": "uuid_or_null",
  "clarification": true_or_false,
  "intent_category": "TRANSACTION" or "DECLARATION" or "SMALL_TALK"
}}

# Constraints
- Do not invent tools.
- intent MUST be the exact tool name from available_tools.
- If unsure, return intent=null and clarification=true.
- intent_category MUST be one of: TRANSACTION, DECLARATION, SMALL_TALK.
"""

        slot_template = """# Task
Extract parameters from user input to fill the request schema.

# Intent
{ctx[intent]}

# Request Schema
{ctx[request_schema]}

# User Input
{ctx[user_input]}

# Output Format
JSON object:
{{
  "payload": {{ ... }},
  "missing_fields": [ ... ],
  "missing_fields_count": 0,
  "execution_ready": true
}}

# Constraints
- Do not invent values.
- List missing required fields in "missing_fields".
- Optional missing fields can be null or omitted.
"""

        clarification_template = """# Task
Ask the user for missing required information.

# Intent
{ctx[intent]}

# Missing Fields
{ctx[missing_fields]}

# Persona
{ctx[persona]}

# Output Format
JSON object:
{{
  "system_output": "Please provide ..."
}}

# Constraints
- Be concise and polite.
- Ask only for missing fields.
- Do not reference schemas or system internals.
"""

        response_template = """# Task
If tool_response is present and non-empty: format it as a natural language message for the user in one concise sentence.
If tool_response is empty or absent: the user asked an informative question (e.g. how to do something). Answer using the retrieved context and user_input; be short and helpful.

# Intent
{ctx[original_intent]}

# User Input
{ctx[user_input]}

# Tool Response
{ctx[tool_response]}

# Persona
{ctx[persona]}

# Output Guidelines
- When tool_response is present: generate only one concise sentence; use product-oriented language; do not list fields or bullets; if success is true, confirm the expense was registered.
- When tool_response is empty: answer the user question using the provided context; be concise.
- Do not mention status codes, endpoints, requests, or payloads.

# Output Format
JSON object:
{{
  "system_output": "..."
}}

# Constraints
- Respect persona language, tone, style.
- Be concise, clear and helpful.
"""

        prompts = [
            (
                PROMPT_INTENT_ID,
                "IntentToolSelectionNode",
                intent_template,
                {
                    "type": "object",
                    "properties": {
                        "intent": {"type": ["string", "null"]},
                        "tool_config_id": {
                            "type": ["string", "null"],
                            "format": "uuid",
                        },
                        "clarification": {"type": "boolean"},
                        "intent_category": {
                            "type": "string",
                            "enum": ["TRANSACTION", "DECLARATION", "SMALL_TALK"],
                        },
                    },
                    "required": ["intent", "tool_config_id", "clarification"],
                },
            ),
            (
                PROMPT_SLOT_ID,
                "ParamExtractionNode",
                slot_template,
                {
                    "type": "object",
                    "properties": {
                        "payload": {"type": "object"},
                        "missing_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "missing_fields_count": {"type": "integer"},
                        "execution_ready": {"type": "boolean"},
                    },
                    "required": [
                        "payload",
                        "missing_fields",
                        "missing_fields_count",
                        "execution_ready",
                    ],
                },
            ),
            (
                PROMPT_CLARIFICATION_ID,
                "ClarificationNode",
                clarification_template,
                {
                    "type": "object",
                    "properties": {"system_output": {"type": "string"}},
                    "required": ["system_output"],
                },
            ),
            (
                PROMPT_RESPONSE_ID,
                "ResponseNode",
                response_template,
                {
                    "type": "object",
                    "properties": {"system_output": {"type": "string"}},
                    "required": ["system_output"],
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

            if existing is None:
                frozen_hash = _calculate_frozen_hash(template_text)
                output_schema_str = json.dumps(output_schema, separators=(",", ":"))
                output_schema_id = (
                    output_schema_str if len(output_schema_str) <= 128 else None
                )
                prompt = NodePrompt(
                    prompt_id=prompt_id,
                    node_type=node_type,
                    template_text=template_text,
                    output_schema_id=output_schema_id,
                    version=1,
                    frozen_hash=frozen_hash,
                    is_active=True,
                    description=f"Prompt for {node_type}",
                    created_by=PRINCIPAL_SYSTEM,
                )
                session.add(prompt)

        await session.commit()
