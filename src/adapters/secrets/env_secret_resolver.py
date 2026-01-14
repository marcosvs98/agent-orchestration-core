import os

from domain.tools.ports.secret_resolver import SecretResolverPort
from exceptions.service_exceptions import DomainValidationException


class EnvSecretResolver(SecretResolverPort):
    async def resolve(self, *, secret_ref: str) -> str:
        if not secret_ref.startswith("env:"):
            raise DomainValidationException(message="unsupported_secret_ref")
        env_key = secret_ref.removeprefix("env:")
        value = os.getenv(env_key)
        if value is None or not value:
            raise DomainValidationException(message="secret_not_found")
        return value
