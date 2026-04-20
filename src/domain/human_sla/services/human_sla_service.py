from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from exceptions.service_exceptions import NotFoundServiceException

from domain.human_sla.repositories.human_sla_policy_repository import (
    HumanSLAPolicyRepository,
)
from domain.human_sla.repositories.human_sla_repository import HumanSLARepository
from domain.human_sla.schemas.human_sla_policy import HumanSLAPolicy
from domain.human_sla.schemas.sla_case import (
    SLACaseCreate,
    SLACaseResolve,
    SLACaseResponse,
    SLAFallbackReason,
    SLAStatus,
)


class HumanSLAService:
    def __init__(
        self,
        repository: HumanSLARepository,
        policy_repository: HumanSLAPolicyRepository,
    ) -> None:
        self.repository = repository
        self.policy_repository = policy_repository

    async def resolve_policy(
        self,
        tenant_id: UUID,
        node: str,
        fallback_reason: str,
    ) -> HumanSLAPolicy | None:
        return await self.policy_repository.resolve_policy(
            tenant_id=tenant_id,
            node=node,
            fallback_reason=fallback_reason,
        )

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

    async def get_or_create_open_case_for_fallback(
        self,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        node_run_id: UUID,
        interaction_id: UUID | None,
        user_id: str,
        node: str,
        fallback_reason: SLAFallbackReason,
        opened_at: datetime,
    ) -> SLACaseResponse | None:
        existing = await self.repository.get_last_open_case_for_session(
            tenant_id=tenant_id, session_id=session_id
        )
        if existing is not None:
            return SLACaseResponse.model_validate(existing)
        reason_str = (
            fallback_reason.value
            if isinstance(fallback_reason, SLAFallbackReason)
            else str(fallback_reason)
        )
        policy = await self.policy_repository.resolve_policy(
            tenant_id=tenant_id, node=node, fallback_reason=reason_str
        )
        if policy is not None:
            priority = policy.initial_priority
            sla_target_at = (
                opened_at.replace(tzinfo=timezone.utc)
                + timedelta(hours=policy.target_response_hours)
                if policy.target_response_hours is not None
                else None
            )
            human_sla_policy_id = policy.human_sla_policy_id
            current_escalation_level = 0
        else:
            priority = None
            sla_target_at = None
            human_sla_policy_id = None
            current_escalation_level = 0
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
            human_sla_policy_id=human_sla_policy_id,
            current_escalation_level=current_escalation_level,
        )
        created_case = await self.repository.create_case(case_create)
        if created_case is None:
            return None
        return SLACaseResponse.model_validate(created_case)

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

    async def evaluate_sla(self, case_id: UUID, tenant_id: UUID) -> None:
        case = await self.repository.get_case(sla_case_id=case_id, tenant_id=tenant_id)
        if case is None or case.human_sla_policy_id is None:
            return
        policy = await self.policy_repository.get_policy_with_rules(case.human_sla_policy_id)
        if policy is None:
            return
        now = datetime.now(timezone.utc)
        opened = (
            case.opened_at.replace(tzinfo=timezone.utc)
            if case.opened_at.tzinfo is None
            else case.opened_at
        )
        elapsed_hours = (now - opened).total_seconds() / 3600.0
        for r in policy.escalation_rules:
            if elapsed_hours >= r.trigger_after_hours and r.level > case.current_escalation_level:
                await self.repository.update_case_escalation(
                    sla_case_id=case_id,
                    tenant_id=tenant_id,
                    priority=r.new_priority,
                    level=r.level,
                )
                case = await self.repository.get_case(sla_case_id=case_id, tenant_id=tenant_id)
                if case is None:
                    return
        if (
            policy.target_resolution_hours is not None
            and elapsed_hours >= policy.target_resolution_hours
        ):
            await self.repository.update_case_sla_breached(sla_case_id=case_id, tenant_id=tenant_id)
