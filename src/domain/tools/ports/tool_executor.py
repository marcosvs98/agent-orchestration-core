from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class ToolExecutorPort(ABC):
    @abstractmethod
    async def execute_http(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict,
        timeout_seconds: float,
    ) -> dict:
        raise NotImplementedServiceException()
