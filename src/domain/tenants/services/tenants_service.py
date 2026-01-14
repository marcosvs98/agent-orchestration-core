from domain.tenants.ports.service import TenantsServicePort
from exceptions.service_exceptions import NotImplementedServiceException


class TenantsService(TenantsServicePort):
    async def get_current(self):
        raise NotImplementedServiceException()

    async def get_settings(self):
        raise NotImplementedServiceException()
