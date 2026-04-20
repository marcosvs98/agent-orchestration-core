import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status

from domain.common.schemas.change import ChangeRequest
from domain.rag.schemas.rag import (
    RagChunk,
    RagChunkingRule,
    RagChunkingRuleCreate,
    RagChunkingRuleUpdateHttpBody,
    RagConfig,
    RagConfigCreate,
    RagContext,
    RagDocument,
    RagDocumentCreate,
    RagDocumentsIngestBatchAccepted,
    RagIngestFromMediaRequest,
    RagRetrievalPreviewRequest,
    VectorStore,
    VectorStoreCreate,
)
from domain.rag.services.rag_media_ingest_service import RagMediaIngestService
from domain.rag.services.rag_service import RagService
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.governance.schemas.scopes import Scope
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    DomainValidationException,
)
from utils.auth import AuthContext, get_auth_context

MAX_RAG_DOCUMENTS_INGEST_BATCH = 10000


class RagController:
    """HTTP controller for RAG configuration."""

    def __init__(
        self,
        service: RagService,
        runtime_service: RagRuntimeService,
        media_ingest_service: RagMediaIngestService | None = None,
    ) -> None:
        self.service = service
        self.runtime_service = runtime_service
        self._media_ingest_service = media_ingest_service
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
            "/rag-configs/{rag_config_id}:validate",
            self.validate_rag_config,
            methods=["POST"],
            response_model=RagConfig,
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
            response_model=RagDocumentsIngestBatchAccepted,
            status_code=status.HTTP_202_ACCEPTED,
        )
        r(
            "/rag-configs/{rag_config_id}/documents:ingestFromMedia",
            self.ingest_document_from_media,
            methods=["POST"],
            response_model=RagDocumentsIngestBatchAccepted,
            status_code=status.HTTP_202_ACCEPTED,
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
        r(
            "/rag-chunking-rules",
            self.list_chunking_rules,
            methods=["GET"],
            response_model=list[RagChunkingRule],
        )
        r(
            "/rag-chunking-rules",
            self.create_chunking_rule,
            methods=["POST"],
            response_model=RagChunkingRule,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/rag-chunking-rules/{rag_chunking_rule_id}",
            self.update_chunking_rule,
            methods=["PATCH"],
            response_model=RagChunkingRule,
        )
        r(
            "/rag-retrieval:preview",
            self.preview_rag_retrieval,
            methods=["POST"],
            response_model=RagContext,
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

    async def validate_rag_config(
        self,
        rag_config_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagConfig:
        self._ensure_scope(auth, Scope.RagConfigsValidate)
        return await self.service.validate_rag_config(
            tenant_id=auth.tenant_id,
            rag_config_id=rag_config_id,
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
        payload: list[RagDocumentCreate],
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagDocumentsIngestBatchAccepted:
        rag_config_uuid = UUID(rag_config_id)
        if not payload:
            raise DomainValidationException(message="rag_documents_required")
        if len(payload) > MAX_RAG_DOCUMENTS_INGEST_BATCH:
            raise DomainValidationException(message="rag_documents_batch_too_large")

        job_id = uuid4()
        accepted = RagDocumentsIngestBatchAccepted(
            rag_config_id=rag_config_uuid,
            job_id=job_id,
            accepted_count=len(payload),
        )

        async def _run_batch() -> None:
            try:
                await self.runtime_service.ingest_documents_batch(
                    tenant_id=auth.tenant_id,
                    rag_config_id=rag_config_uuid,
                    documents=payload,
                )
            except Exception:
                pass

        asyncio.create_task(_run_batch())
        return accepted

    async def ingest_document_from_media(
        self,
        rag_config_id: str,
        body: RagIngestFromMediaRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagDocumentsIngestBatchAccepted:
        if self._media_ingest_service is None:
            raise DomainValidationException(message="rag_media_ingest_unconfigured")
        self._ensure_scope(auth, Scope.RagConfigsCreate)
        rag_config_uuid = UUID(rag_config_id)
        return await self._media_ingest_service.schedule_ingest_from_media(
            tenant_id=auth.tenant_id,
            rag_config_id=rag_config_uuid,
            body=body,
        )

    async def list_documents(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        rag_config_id: UUID | None = Query(default=None),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagDocument]:
        return await self.runtime_service.list_documents(
            tenant_id=auth.tenant_id,
            limit=limit,
            rag_config_id=rag_config_id,
        )

    async def list_chunks(
        self,
        document_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagChunk]:
        return await self.runtime_service.list_chunks(document_id=UUID(document_id), limit=limit)

    async def list_chunking_rules(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RagChunkingRule]:
        self._ensure_scope(auth, Scope.RagConfigsList)
        return await self.service.list_chunking_rules(tenant_id=auth.tenant_id, limit=limit)

    async def create_chunking_rule(
        self,
        payload: RagChunkingRuleCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagChunkingRule:
        self._ensure_scope(auth, Scope.RagConfigsCreate)
        return await self.service.create_chunking_rule(
            tenant_id=auth.tenant_id,
            payload=payload,
            principal_id=auth.principal_id,
        )

    async def update_chunking_rule(
        self,
        rag_chunking_rule_id: str,
        body: RagChunkingRuleUpdateHttpBody,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagChunkingRule:
        self._ensure_scope(auth, Scope.RagConfigsCreate)
        return await self.service.update_chunking_rule(
            tenant_id=auth.tenant_id,
            rag_chunking_rule_id=rag_chunking_rule_id,
            payload=body.rule,
            principal_id=auth.principal_id,
            change_request=body.change,
        )

    async def preview_rag_retrieval(
        self,
        body: RagRetrievalPreviewRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagContext:
        self._ensure_scope(auth, Scope.RagConfigsList)
        return await self.runtime_service.get_context(
            tenant_id=auth.tenant_id,
            rag_config_id=body.rag_config_id,
            user_id=auth.principal_id,
            user_input=body.user_input,
            filters_override=body.filters_override,
            top_k_override=body.top_k_override,
        )
