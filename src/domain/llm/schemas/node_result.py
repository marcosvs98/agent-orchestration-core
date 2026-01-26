from typing import Literal

from pydantic import BaseModel


class NodeResult(BaseModel):
    output: dict
    next_action: Literal["continue", "route_human"] = "continue"


class SlotFillingResult(NodeResult):
    payload: dict
    is_valid: bool
    errors: list[str] = []

    def __init__(self, **data):
        super().__init__(**data)
        if "output" not in data:
            self.output = {
                "payload": self.payload,
                "is_valid": self.is_valid,
                "errors": self.errors,
            }
