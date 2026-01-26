from fastapi import APIRouter, Depends, Query, status

from domain.common.schemas.change import ChangeRequest
from domain.rag.schemas.rag import RagConfig, RagConfigCreate, VectorStore
from domain.rag.services.rag_service import RagService
from utils.auth import AuthContext, get_auth_context


class RagController:
    """HTTP controller for RAG configuration."""

    def __init__(self, service: RagService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["rag"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/rag-configs",
            self.list_rag_configs,
            methods=["GET"],
            response_model=list[RagConfig],
        )
        r(
            "/rag-configs",
            self.create_rag_config,
            methods=["POST"],
            response_model=RagConfig,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/rag-configs/{rag_config_id}:publish",
            self.publish_rag_config,
            methods=["POST"],
            response_model=RagConfig,
        )
        r(
            "/rag-configs/{rag_config_id}:deprecate",
            self.deprecate_rag_config,
            methods=["POST"],
            response_model=RagConfig,
        )
        r(
            "/rag-configs/{rag_config_id}:disable",
            self.disable_rag_config,
            methods=["POST"],
            response_model=RagConfig,
        )
        r(
            "/vector-stores",
            self.list_vector_stores,
            methods=["GET"],
            response_model=list[VectorStore],
        )

    async def list_rag_configs(
        self,
        status_filter: list[str] | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagConfig]:
        return await self.service.list_rag_configs(
            tenant_id=auth.tenant_id, status_filter=status_filter, limit=limit
        )

    async def create_rag_config(
        self,
        rag_config_create: RagConfigCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagConfig:
        return await self.service.create_rag_config(
            tenant_id=auth.tenant_id,
            rag_config_create=rag_config_create,
            principal_id=auth.principal_id,
        )

    async def publish_rag_config(
        self,
        rag_config_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagConfig:
        return await self.service.publish_rag_config(
            tenant_id=auth.tenant_id,
            rag_config_id=rag_config_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def deprecate_rag_config(
        self,
        rag_config_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagConfig:
        return await self.service.deprecate_rag_config(
            tenant_id=auth.tenant_id,
            rag_config_id=rag_config_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def disable_rag_config(
        self,
        rag_config_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagConfig:
        return await self.service.disable_rag_config(
            tenant_id=auth.tenant_id,
            rag_config_id=rag_config_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def list_vector_stores(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> list[VectorStore]:
        return await self.service.list_vector_stores()
