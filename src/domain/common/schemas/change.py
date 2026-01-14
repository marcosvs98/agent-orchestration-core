from pydantic import BaseModel


class ChangeRequest(BaseModel):
    change_type: str
    justification: str
