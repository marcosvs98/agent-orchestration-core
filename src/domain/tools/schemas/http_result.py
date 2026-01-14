from pydantic import BaseModel


class HttpToolResult(BaseModel):
    status_code: int
    headers: dict[str, str]
    text: str
