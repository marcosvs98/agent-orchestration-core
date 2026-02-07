from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict

from pydantic import BaseModel, Field


class GuardrailDecisionType(StrEnum):
    ALLOW = "ALLOW"
    DEGRADE = "DEGRADE"
    BLOCK = "BLOCK"


class ObservationLevel(StrEnum):
    DEBUG = "DEBUG"
    DEFAULT = "DEFAULT"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GuardrailDecision(BaseModel):
    decision: GuardrailDecisionType
    reason_code: str
    applied_limits: Dict[str, Any] = Field(default_factory=dict)
    overrides: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
