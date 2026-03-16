from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from domain.human_sla.schemas.sla_case import (
    SLACaseAssign,
    SLACaseResolve,
    SLACaseResponse,
    SLAStatus,
)
from domain.human_sla.services.human_sla_service import HumanSLAService
from utils.auth import AuthContext, get_auth_context


class HumanSLAController:
    def __init__(self, service: HumanSLAService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1/sla-cases",
            tags=["human-sla"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "",
            self.list_cases,
            methods=["GET"],
            response_model=list[SLACaseResponse],
            status_code=status.HTTP_200_OK,
        )
        r(
            "/{sla_case_id}",
            self.get_case,
            methods=["GET"],
            response_model=SLACaseResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/{sla_case_id}/assign",
            self.assign_case,
            methods=["PATCH"],
            response_model=SLACaseResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/{sla_case_id}/resolve",
            self.resolve_case,
            methods=["PATCH"],
            response_model=SLACaseResponse,
            status_code=status.HTTP_200_OK,
        )

    async def list_cases(
        self,
        status_filter: SLAStatus | None = Query(default=None, alias="status"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[SLACaseResponse]:
        return await self.service.list_cases(
            tenant_id=auth.tenant_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

    async def get_case(
        self,
        sla_case_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> SLACaseResponse:
        return await self.service.get_case_detail(
            tenant_id=auth.tenant_id,
            sla_case_id=sla_case_id,
        )

    async def assign_case(
        self,
        sla_case_id: UUID,
        payload: SLACaseAssign,
        auth: AuthContext = Depends(get_auth_context),
    ) -> SLACaseResponse:
        return await self.service.assign_case(
            tenant_id=auth.tenant_id,
            sla_case_id=sla_case_id,
            human_agent_id=payload.human_agent_id,
        )

    async def resolve_case(
        self,
        sla_case_id: UUID,
        payload: SLACaseResolve,
        auth: AuthContext = Depends(get_auth_context),
    ) -> SLACaseResponse:
        return await self.service.resolve_case(
            tenant_id=auth.tenant_id,
            sla_case_id=sla_case_id,
            payload=payload,
        )
