from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class ToolsServicePort(ABC):
    @abstractmethod
    async def import_tool(self, tool_import_request):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_tools(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_tool_config(self, tool_config_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_agent_version_tool_binding(
        self, agent_version_tool_binding_create
    ):
        raise NotImplementedServiceException()
