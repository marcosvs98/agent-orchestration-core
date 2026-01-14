from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class FlowsServicePort(ABC):
    @abstractmethod
    async def list_flows(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_flow(self, flow_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_flow(self, flow_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_flow_versions(self, flow_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_flow_version(self, flow_id: str, flow_version_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_nodes(self, flow_id: str, flow_version_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_node(self, node_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_routers(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_router(self, router_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_routing_rule(self, routing_rule_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_condition_expression(self, condition_expression_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def validate_flow_version(self, *, tenant_id, flow_id: str, flow_version_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def publish_flow_version(self, *, tenant_id, flow_id: str, flow_version_id: str, principal_id: str, change_request):
        raise NotImplementedServiceException()

    @abstractmethod
    async def activate_flow_version(self, *, tenant_id, flow_id: str, flow_version_id: str, principal_id: str, change_request):
        raise NotImplementedServiceException()

    @abstractmethod
    async def rollback_flow_version(self, *, tenant_id, flow_id: str, flow_version_id: str, principal_id: str, change_request):
        raise NotImplementedServiceException()
