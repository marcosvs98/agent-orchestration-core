from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import Any, Dict, Literal
from uuid import UUID, uuid4

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "pyproject.toml").exists():
        sys.path.insert(0, str(_candidate / "src"))
        break
else:
    raise SystemExit("repository root not found")

from domain.execution.services.graph_runtime.types import ExecutionContext  # noqa: E402


class NullSpan:
    def __enter__(self) -> "NullSpan":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    @staticmethod
    def update(*args: Any, **kwargs: Any) -> None:
        return None

    @staticmethod
    def success(*args: Any, **kwargs: Any) -> None:
        return None

    @staticmethod
    def error(*args: Any, **kwargs: Any) -> None:
        return None


class NullTracer:
    @staticmethod
    def observe(**kwargs: Any) -> NullSpan:
        return NullSpan()

    @staticmethod
    def shutdown() -> None:
        return None


def build_context(
    *,
    state: Dict[str, Any] | None = None,
    input_payload: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
    node_run_id: UUID | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid4(),
        interaction_id=uuid4(),
        user_id="example-user",
        session_id=uuid4(),
        input_payload=input_payload if input_payload is not None else {"user_input": "hello"},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
        current_node_run_id=node_run_id or uuid4(),
        state=state or {},
        metadata=metadata or {},
    )


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def field(label: str, value: Any) -> None:
    print(f"  {label:.<38} {value}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAILED: {message}")
    print(f"  ok  {message}")
