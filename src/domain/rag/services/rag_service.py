from domain.rag.ports.service import RagServicePort
from exceptions.service_exceptions import NotImplementedServiceException


class RagService(RagServicePort):
    async def list_rag_configs(self):
        raise NotImplementedServiceException()

    async def create_rag_config(self, rag_config_create):
        raise NotImplementedServiceException()

    async def list_vector_stores(self):
        raise NotImplementedServiceException()
