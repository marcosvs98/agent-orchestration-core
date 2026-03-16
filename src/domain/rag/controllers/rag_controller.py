from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from domain.common.schemas.change import ChangeRequest
from domain.rag.schemas.rag import (
    RagChunk,
    RagConfig,
    RagConfigCreate,
    RagDocument,
    RagDocumentCreate,
    VectorStore,
    VectorStoreCreate,
)
from domain.rag.services.rag_service import RagService
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.governance.schemas.scopes import Scope
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context


class RagController:
    """HTTP controller for RAG configuration."""

    def __init__(self, service: RagService, runtime_service: RagRuntimeService) -> None:
        self.service = service
        self.runtime_service = runtime_service
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
        r(
            "/vector-stores",
            self.create_vector_store,
            methods=["POST"],
            response_model=VectorStore,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/rag-configs/{rag_config_id}/documents:ingest",
            self.ingest_document,
            methods=["POST"],
            response_model=RagDocument,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/rag-documents",
            self.list_documents,
            methods=["GET"],
            response_model=list[RagDocument],
        )
        r(
            "/rag-documents/{document_id}/chunks",
            self.list_chunks,
            methods=["GET"],
            response_model=list[RagChunk],
        )

    @staticmethod
    def _ensure_scope(auth: AuthContext, scope: Scope) -> None:
        if scope.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")

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
        self._ensure_scope(auth, Scope.VectorStoresList)
        return await self.service.list_vector_stores(tenant_id=auth.tenant_id)

    async def create_vector_store(
        self,
        vector_store_create: VectorStoreCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> VectorStore:
        self._ensure_scope(auth, Scope.VectorStoresCreate)
        return await self.service.create_vector_store(
            tenant_id=auth.tenant_id,
            vector_store_create=vector_store_create,
        )

    async def ingest_document(
        self,
        rag_config_id: str,
        payload: RagDocumentCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagDocument:
        return await self.runtime_service.ingest_document(
            tenant_id=auth.tenant_id,
            rag_config_id=UUID(rag_config_id),
            document=payload,
        )

    async def list_documents(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagDocument]:
        return await self.runtime_service.list_documents(
            tenant_id=auth.tenant_id, limit=limit
        )

    async def list_chunks(
        self,
        document_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagChunk]:
        return await self.runtime_service.list_chunks(
            document_id=UUID(document_id), limit=limit
        )
