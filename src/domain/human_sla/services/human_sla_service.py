from __future__ import annotations

from datetime import datetime
from uuid import UUID

from exceptions.service_exceptions import NotFoundServiceException

from domain.human_sla.repositories.human_sla_repository import HumanSLARepository
from domain.human_sla.schemas.sla_case import (
    SLACaseCreate,
    SLACaseResolve,
    SLACaseResponse,
    SLAFallbackReason,
    SLAStatus,
)


class HumanSLAService:
    def __init__(self, repository: HumanSLARepository) -> None:
        self.repository = repository

    async def create_case_for_fallback(
        self,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        node_run_id: UUID,
        interaction_id: UUID | None,
        user_id: str,
        fallback_reason: SLAFallbackReason,
        opened_at: datetime,
        priority: str | None = None,
        sla_target_at: datetime | None = None,
    ) -> UUID | None:
        case_create = SLACaseCreate(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            node_run_id=node_run_id,
            interaction_id=interaction_id,
            user_id=user_id,
            priority=priority,
            fallback_reason=fallback_reason,
            opened_at=opened_at,
            sla_target_at=sla_target_at,
        )
        created_case = await self.repository.create_case(case_create)
        if created_case is None:
            return None
        return created_case.sla_case_id

    async def list_open_cases(
        self, tenant_id: UUID, limit: int, offset: int
    ) -> list[SLACaseResponse]:
        cases = await self.repository.list_cases(
            tenant_id=tenant_id,
            status=SLAStatus.OPEN,
            limit=limit,
            offset=offset,
        )
        return [SLACaseResponse.model_validate(case) for case in cases]

    async def list_cases(
        self,
        tenant_id: UUID,
        status: SLAStatus | None,
        limit: int,
        offset: int,
    ) -> list[SLACaseResponse]:
        cases = await self.repository.list_cases(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [SLACaseResponse.model_validate(case) for case in cases]

    async def get_case_detail(self, tenant_id: UUID, sla_case_id: UUID) -> SLACaseResponse:
        case = await self.repository.get_case(sla_case_id=sla_case_id, tenant_id=tenant_id)
        if case is None:
            raise NotFoundServiceException(message="sla_case_not_found")
        return SLACaseResponse.model_validate(case)

    async def assign_case(
        self, tenant_id: UUID, sla_case_id: UUID, human_agent_id: str
    ) -> SLACaseResponse:
        case = await self.repository.assign_case(
            tenant_id=tenant_id,
            sla_case_id=sla_case_id,
            human_agent_id=human_agent_id,
        )
        if case is None:
            raise NotFoundServiceException(message="sla_case_not_found")
        return SLACaseResponse.model_validate(case)

    async def resolve_case(
        self,
        tenant_id: UUID,
        sla_case_id: UUID,
        payload: SLACaseResolve,
    ) -> SLACaseResponse:
        case = await self.repository.resolve_case(
            tenant_id=tenant_id,
            sla_case_id=sla_case_id,
            resolution_status=payload.resolution_status,
            resolution_summary=payload.resolution_summary,
            human_agent_id=payload.human_agent_id,
        )
        if case is None:
            raise NotFoundServiceException(message="sla_case_not_found")
        return SLACaseResponse.model_validate(case)
