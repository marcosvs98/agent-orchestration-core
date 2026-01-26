from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class TenantsServicePort(ABC):
    @abstractmethod
    async def create(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_current(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_settings(self):
        raise NotImplementedServiceException()
