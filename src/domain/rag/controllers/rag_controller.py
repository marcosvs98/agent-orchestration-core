from fastapi import APIRouter, Depends, status

from domain.rag.schemas.rag import RagConfig, RagConfigCreate, VectorStore
from domain.rag.services.rag_service import RagService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException
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
        r("/rag-configs", self.list_rag_configs, methods=["GET"], response_model=list[RagConfig], responses=self._resp405())
        r("/rag-configs", self.create_rag_config, methods=["POST"], response_model=RagConfig, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/rag-configs/{rag_config_id}:publish", self.publish_rag_config, methods=["POST"], response_model=RagConfig, responses=self._resp405())
        r("/rag-configs/{rag_config_id}:deprecate", self.deprecate_rag_config, methods=["POST"], response_model=RagConfig, responses=self._resp405())
        r("/rag-configs/{rag_config_id}:disable", self.disable_rag_config, methods=["POST"], response_model=RagConfig, responses=self._resp405())
        r("/vector-stores", self.list_vector_stores, methods=["GET"], response_model=list[VectorStore], responses=self._resp405())

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_rag_configs(
        self,
        status_filter: list[str] | None = None,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[RagConfig]:
        raise MethodNotAllowedPlaceholderException()

    async def create_rag_config(self, __: RagConfigCreate, _: AuthContext = Depends(get_auth_context)) -> RagConfig:
        raise MethodNotAllowedPlaceholderException()

    async def publish_rag_config(self, rag_config_id: str, _: AuthContext = Depends(get_auth_context)) -> RagConfig:
        raise MethodNotAllowedPlaceholderException()

    async def deprecate_rag_config(self, rag_config_id: str, _: AuthContext = Depends(get_auth_context)) -> RagConfig:
        raise MethodNotAllowedPlaceholderException()

    async def disable_rag_config(self, rag_config_id: str, _: AuthContext = Depends(get_auth_context)) -> RagConfig:
        raise MethodNotAllowedPlaceholderException()

    async def list_vector_stores(self, _: AuthContext = Depends(get_auth_context)) -> list[VectorStore]:
        raise MethodNotAllowedPlaceholderException()
