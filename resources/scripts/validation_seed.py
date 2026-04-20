"""Stable UUID aliases for ``validation_integration`` tests (see demo seeds)."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from seeds.demo.ids import (  # noqa: E402
    ACCESS_POLICY_VERSION_V1_ID,
    AGENT_DEMO_ID,
    AGENT_VERSION_V1_ID,
    BILLING_POLICY_VERSION_V1_ID,
    FLOW_DEMO_ID,
    FLOW_VERSION_V1_ID,
    NODE_INTENT_ID,
    POLICY_VERSION_V1_ID,
    RATE_LIMIT_POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
)

# --- Aliases used by tests/integration/validation_integration/ ---

TENANT_ID = TENANT_DEMO_ID
FLOW_ID = FLOW_DEMO_ID
FLOW_VERSION_ID = FLOW_VERSION_V1_ID
AGENT_ID = AGENT_DEMO_ID
AGENT_VERSION_ID = AGENT_VERSION_V1_ID
NODE_ID = NODE_INTENT_ID
POLICY_VERSION_ID = POLICY_VERSION_V1_ID
BILLING_POLICY_VERSION_ID = BILLING_POLICY_VERSION_V1_ID
ACCESS_POLICY_VERSION_ID = ACCESS_POLICY_VERSION_V1_ID
RATE_LIMIT_VERSION_ID = RATE_LIMIT_POLICY_VERSION_V1_ID

# Placeholder: must match a seeded ``session`` row when running validation against Postgres.
SESSION_ID = UUID("00000000-0000-0000-0000-000000000120")

# No flow uses this id as an active deployment (fail-closed check).
DRAFT_FLOW_ID = UUID("00000000-0000-0000-0000-00000000f000")

# Second flow version kept as DRAFT in extended seeds; tests assert draft vs published split.
DRAFT_FLOW_VERSION_ID = UUID("00000000-0000-0000-0000-000000000702")

# Execution-limit policy version (add matching seed before enabling validation job).
EXEC_LIMIT_VERSION_ID = UUID("00000000-0000-0000-0000-000000001299")

__all__ = [
    "ACCESS_POLICY_VERSION_ID",
    "AGENT_ID",
    "AGENT_VERSION_ID",
    "BILLING_POLICY_VERSION_ID",
    "DRAFT_FLOW_ID",
    "DRAFT_FLOW_VERSION_ID",
    "EXEC_LIMIT_VERSION_ID",
    "FLOW_ID",
    "FLOW_VERSION_ID",
    "NODE_ID",
    "POLICY_VERSION_ID",
    "RATE_LIMIT_VERSION_ID",
    "SESSION_ID",
    "TENANT_ID",
]
