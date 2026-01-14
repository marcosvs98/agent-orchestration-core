from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class SecretResolverPort(ABC):
    @abstractmethod
    async def resolve(self, *, secret_ref: str) -> str:
        raise NotImplementedServiceException()
