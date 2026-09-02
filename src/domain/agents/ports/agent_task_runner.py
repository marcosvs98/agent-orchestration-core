from __future__ import annotations

from typing import Protocol

from domain.agents.schemas.a2a import A2ATaskExecution, A2ATaskExecutionResult


class AgentTaskRunnerPort(Protocol):
    """Transport for one A2A task.

    The in-process implementation is the agent runtime itself; a remote implementation would
    speak JSON-RPC ``message/send`` to another A2A server. Keeping this the only seam means the
    orchestration domain never learns which side of the wire the peer agent lives on.
    """

    async def run_a2a_task(
        self, *, execution: A2ATaskExecution
    ) -> A2ATaskExecutionResult:  # pragma: no cover - interface
        ...
