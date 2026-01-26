from typing import TypedDict


class ToolConfigConfig(TypedDict, total=False):
    url: str
    method: str
    request_schema: dict
    response_schema: dict
    operation_id: str
