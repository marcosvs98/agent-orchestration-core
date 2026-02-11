from __future__ import annotations

from uuid import UUID

from domain.context.schemas.context_layers import SessionContextSnapshot
from domain.execution.repositories.execution_repository import ExecutionRepository
from exceptions.service_exceptions import NotFoundServiceException


class SessionContextService:
    def __init__(self, repository: ExecutionRepository) -> None:
        self.repository = repository

    async def load_snapshot(self, *, flow_run_id: UUID) -> SessionContextSnapshot:
        graph_state = await self.repository.get_graph_state(flow_run_id)
        if graph_state is None:
            return SessionContextSnapshot(flow_run_id=flow_run_id)
        payload = graph_state.state or {}
        return SessionContextSnapshot(
            flow_run_id=flow_run_id,
            current_node_id=payload.get("current_node_id"),
            resume_to_node_id=payload.get("resume_to_node_id"),
            state=payload.get("state") or {},
            memory=payload.get("memory") or [],
        )

    async def persist_snapshot(self, *, snapshot: SessionContextSnapshot) -> None:
        flow_run = await self.repository.get_flow_run(snapshot.flow_run_id)
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        state = {
            "current_node_id": snapshot.current_node_id,
            "resume_to_node_id": snapshot.resume_to_node_id,
            "state": snapshot.state,
            "memory": snapshot.memory,
        }
        await self.repository.upsert_graph_state(
            flow_run_id=snapshot.flow_run_id,
            state=state,
            last_node_run_id=flow_run.current_node_run_id,
        )
