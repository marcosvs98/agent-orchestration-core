from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from domain.flows.schemas.graph_node_config import validate_node_config


def test_validate_node_config_accepts_optional_rag_pipeline() -> None:
    validate_node_config(
        "IntentClassifier",
        {
            "llm": {},
            "rag_pipeline": {
                "retriever_when": "always",
                "retriever_profile_id": str(uuid.uuid4()),
            },
        },
    )


def test_validate_node_config_rejects_invalid_rag_pipeline_when() -> None:
    with pytest.raises(ValidationError):
        validate_node_config(
            "IntentClassifier",
            {"rag_pipeline": {"retriever_when": "sometimes"}},
        )
