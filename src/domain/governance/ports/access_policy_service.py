from abc import ABC, abstractmethod
from uuid import UUID
from exceptions.service_exceptions import NotImplementedServiceException


class AccessPolicyServicePort(ABC):
    @abstractmethod
    async def authorize(
        self,
        *,
        tenant_id: UUID,
        principal_type: str,
        principal_id: str,
        scopes: set[str],
        action: str,
    ) -> None:
        raise NotImplementedServiceException()
