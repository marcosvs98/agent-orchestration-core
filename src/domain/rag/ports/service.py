from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class RagServicePort(ABC):
    @abstractmethod
    async def list_rag_configs(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_rag_config(self, rag_config_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_vector_stores(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_vector_store(self, vector_store_create):
        raise NotImplementedServiceException()
