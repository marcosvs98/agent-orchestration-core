from __future__ import annotations

import asyncio
import cProfile
import pstats
import sys
import uuid
from pathlib import Path
from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from containers import ApplicationContainer
from domain.execution.schemas.execution import FlowRunCreate, FlowRunInput
from resources.scripts.seeds.demo.ids import FLOW_VERSION_V1_ID, TENANT_DEMO_ID
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext


# ---------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = PROJECT_ROOT / "src"

for path in (SRC_PATH, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


# ---------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------

def build_auth() -> AuthContext:
    return AuthContext(
        tenant_id=TENANT_DEMO_ID,
        principal_type="human",
        principal_id="script",
        scopes={"execution:flow_run:create"},
        token_issuer="script",
        token_audience="script",
        expires_at=0,
    )


def build_flow_run(user_input: str) -> FlowRunCreate:
    return FlowRunCreate(
        flow_version_id=FLOW_VERSION_V1_ID,
        session_id=uuid.uuid4(),
        user_id="test_user_id",
        correlation_id=uuid.uuid4(),
        input=FlowRunInput(user_input=user_input),
    )


# ---------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------

async def run() -> None:
    container = ApplicationContainer()
    container.init_resources()

    try:
        boundary: ExecutionBoundary = (
            container.execution.execution_boundary()
        )

        await boundary.ingest_interaction_and_create_flow_run(
            auth=build_auth(),
            endpoint="/core/v1/executions/flow-runs",
            idempotency_key=str(uuid.uuid4()),
            flow_run=build_flow_run(
                "Gastei 1000 reais no mercado na categoria compras para casa, "
                "pago com cartão, usando a conta PF do banco XP, "
                "no cartão XP, no dia 01/01/2026"
            ),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=str(uuid.uuid4()),
        )
    finally:
        container.shutdown_resources()


def main() -> None:
    asyncio.run(run())


# ---------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------

def profile_and_export() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    main()
    profiler.disable()

    prof_path = PROJECT_ROOT / "execute_flow_demo_direct.prof"
    txt_path = PROJECT_ROOT / "execute_flow_demo_direct.txt"

    profiler.dump_stats(str(prof_path))

    with open(txt_path, "w", encoding="utf-8") as f:
        stats = pstats.Stats(profiler, stream=f)

        f.write("\n=== TOP 50 - CUMULATIVE TIME ===\n")
        stats.sort_stats(pstats.SortKey.CUMULATIVE).print_stats(50)

        f.write("\n=== TOP 50 - INTERNAL TIME ===\n")
        stats.sort_stats(pstats.SortKey.TIME).print_stats(50)

        f.write("\n=== TOP 30 - CALL COUNT ===\n")
        stats.sort_stats(pstats.SortKey.CALLS).print_stats(30)

    print(f"Binary profile saved at: {prof_path}")
    print(f"Text report saved at: {txt_path}")
    print(f"Inspect with: python -m pstats {prof_path} or snakeviz {prof_path}")

if __name__ == "__main__":
    profile_and_export()

