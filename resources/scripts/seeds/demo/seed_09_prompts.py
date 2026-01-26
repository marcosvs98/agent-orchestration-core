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
    PROMPT_INTENT_ID,
    PROMPT_RESPONSE_ID,
    PROMPT_SLOT_ID,
)


def _calculate_frozen_hash(template_text: str) -> str:
    return hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:64]


async def seed_prompts() -> None:
    async with get_db() as session:
        intent_template = """Analyze the user input and select the appropriate tool.

Context:
- Persona: {ctx[persona]}
- User Input: {ctx[user_input]}

Available tools will be provided separately.

Return JSON with:
- intent: string describing the user's intent
- tool_config_id: UUID of the selected tool

Do not invent information. If uncertain, indicate that clarification is needed."""

        slot_template = """Extract parameters from user input to fill the tool request schema.

Context:
- Persona: {ctx[persona]}
- Intent: {ctx[intent]}
- Request Schema: {ctx[request_schema]}

Fill the request schema with values extracted from the user input.

Return JSON with:
- payload: object matching the request_schema

Ensure all required fields are present. If information is missing, indicate which fields need clarification."""

        response_template = """Format the tool response into a natural language message for the user.

Context:
- Persona: {ctx[persona]}
- Tool Response: {ctx[tool_response]}
- Original Intent: {ctx[original_intent]}

Create a clear, concise response in the persona's style and language.

Return JSON with:
- message: string with the formatted response

Keep the response within the persona's max_response_length limit."""

        prompts = [
            (
                PROMPT_INTENT_ID,
                "IntentToolSelectionNode",
                intent_template,
                {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string"},
                        "tool_config_id": {"type": "string", "format": "uuid"},
                    },
                    "required": ["intent", "tool_config_id"],
                },
            ),
            (
                PROMPT_SLOT_ID,
                "ParamExtractionNode",
                slot_template,
                {
                    "type": "object",
                    "properties": {"payload": {"type": "object"}},
                    "required": ["payload"],
                },
            ),
            (
                PROMPT_RESPONSE_ID,
                "ResponseNode",
                response_template,
                {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
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
