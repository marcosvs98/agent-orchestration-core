from __future__ import annotations

import hashlib
import re

from domain.agents.schemas.agents import PersonaConfig
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.prompts.schemas.system_prompt_template import SystemPromptTemplate
from exceptions.service_exceptions import DomainValidationException


class SystemPromptCompiler:
    def __init__(self, tracer: RuntimeTracerPort) -> None:
        self.tracer = tracer

    def render(
        self,
        template: SystemPromptTemplate,
        persona: PersonaConfig,
    ) -> str:
        with self.tracer.observe(
            as_type="chain",
            name="application.prompts.system_prompt_compiler.render",
            input={},
        ):
            template_text = template.template_text
            persona_dict = persona.model_dump()

            placeholders = self._extract_placeholders(template_text)

            for placeholder in placeholders:
                if placeholder not in persona_dict:
                    raise DomainValidationException(
                        message="system_prompt_placeholder_missing",
                        detail=f"placeholder {placeholder} not found in persona model",
                    )

            rendered = template_text
            for placeholder, value in persona_dict.items():
                if placeholder in placeholders:
                    if isinstance(value, list):
                        formatted_value = (
                            "\n".join(f"- {item}" for item in value) if value else ""
                        )
                    else:
                        formatted_value = str(value) if value is not None else ""
                    rendered = rendered.replace(
                        f"{{{{ {placeholder} }}}}", formatted_value
                    )
                    rendered = rendered.replace(
                        f"{{{{{placeholder}}}}}", formatted_value
                    )

            return rendered.strip()

    def _extract_placeholders(self, template_text: str) -> set[str]:
        pattern = r"\{\{\s*(\w+)\s*\}\}"
        matches = re.findall(pattern, template_text)
        return set(matches)

    def compute_hash(self, system_prompt: str) -> str:
        return hashlib.sha256(system_prompt.encode()).hexdigest()
