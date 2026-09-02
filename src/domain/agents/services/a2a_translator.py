from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.agents.schemas.a2a import (
    A2AArtifact,
    A2ADataPart,
    A2AMessage,
    A2APart,
    A2ARole,
    A2ATask,
    A2ATaskState,
    A2ATaskStatus,
    A2ATextPart,
)


class A2ATranslator:
    """Boundary between the AOC execution vocabulary and the A2A wire vocabulary.

    Nothing in the orchestration domain imports A2A types directly; everything crosses here, so
    a protocol revision stays a change to this file plus the schemas it maps.
    """

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def new_task_id() -> str:
        return uuid4().hex

    @staticmethod
    def context_id_for_root_run(root_agent_run_id: UUID) -> str:
        return root_agent_run_id.hex

    def build_request_message(
        self,
        *,
        task_id: str,
        context_id: str,
        instruction: str,
        payload: dict[str, object],
    ) -> A2AMessage:
        parts: list[A2APart] = [A2ATextPart(text=instruction)]
        if payload:
            parts.append(A2ADataPart(data=dict(payload)))
        return A2AMessage(
            message_id=uuid4().hex,
            role=A2ARole.USER,
            parts=parts,
            task_id=task_id,
            context_id=context_id,
        )

    def build_agent_message(
        self,
        *,
        task_id: str,
        context_id: str,
        text: str,
    ) -> A2AMessage:
        return A2AMessage(
            message_id=uuid4().hex,
            role=A2ARole.AGENT,
            parts=[A2ATextPart(text=text)],
            task_id=task_id,
            context_id=context_id,
        )

    def build_task(
        self,
        *,
        task_id: str,
        context_id: str,
        state: A2ATaskState,
        history: list[A2AMessage],
        artifacts: list[A2AArtifact],
        status_message: A2AMessage | None = None,
        metadata: dict[str, object] | None = None,
    ) -> A2ATask:
        return A2ATask(
            id=task_id,
            context_id=context_id,
            status=A2ATaskStatus(
                state=state,
                message=status_message,
                timestamp=self._timestamp(),
            ),
            history=history,
            artifacts=artifacts,
            metadata=dict(metadata) if metadata else None,
        )

    @staticmethod
    def build_output_artifact(
        *,
        index: int,
        name: str,
        description: str | None,
        text: str,
        data: dict[str, object] | None = None,
    ) -> A2AArtifact:
        parts: list[A2APart] = []
        if text:
            parts.append(A2ATextPart(text=text))
        if data:
            parts.append(A2ADataPart(data=dict(data)))
        return A2AArtifact(
            artifact_id=f"{name}-{index}",
            name=name,
            description=description,
            parts=parts,
        )

    @staticmethod
    def task_state_for_run_status(canonical_status: str) -> A2ATaskState:
        mapping = {
            "CREATED": A2ATaskState.SUBMITTED,
            "RUNNING": A2ATaskState.WORKING,
            "COMPLETED": A2ATaskState.COMPLETED,
            "FAILED": A2ATaskState.FAILED,
            "CANCELLED": A2ATaskState.CANCELED,
        }
        return mapping.get(canonical_status, A2ATaskState.UNKNOWN)
