"""BDD fixtures for user input normalization (no HTTP)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def bdd() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=None,
        user_input=None,
        input_parts=None,
        result=None,
        error=None,
    )
