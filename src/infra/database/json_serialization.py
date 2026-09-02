from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from json import dumps
from pathlib import PurePath
from typing import Any
from uuid import UUID


def jsonb_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (UUID, IPv4Address, IPv6Address, PurePath)):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def jsonb_serializer(value: Any) -> str:
    return dumps(value, default=jsonb_default, allow_nan=False)
