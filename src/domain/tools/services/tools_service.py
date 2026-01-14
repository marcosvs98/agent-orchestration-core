from domain.tools.ports.service import ToolsServicePort
from exceptions.service_exceptions import NotImplementedServiceException


class ToolsService(ToolsServicePort):
    async def import_tool(self, tool_import_request):
        raise NotImplementedServiceException()

    async def list_tools(self):
        raise NotImplementedServiceException()

    async def create_tool_config(self, tool_config_create):
        raise NotImplementedServiceException()

    async def create_agent_version_tool_binding(self, agent_version_tool_binding_create):
        raise NotImplementedServiceException()
