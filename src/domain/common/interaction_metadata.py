from typing import Final

END_USER_AUTHORIZATION_METADATA_KEY: Final[str] = "end_user_authorization"

ACCEPTED_END_USER_AUTHORIZATION_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {END_USER_AUTHORIZATION_METADATA_KEY}
)


def resolve_metadata_value(metadata: dict[str, object], key: str) -> object | None:
    value = metadata.get(key)
    if value is not None and (not isinstance(value, str) or value.strip()):
        return value
    return None
