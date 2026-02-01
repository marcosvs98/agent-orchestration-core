from typing import Any

from pydantic import BaseModel


class HttpToolResult(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: Any
