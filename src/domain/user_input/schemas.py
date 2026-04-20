from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TextUserInputPart(BaseModel):
    """Plain text segment from the user."""

    model_config = {"extra": "forbid"}

    type: Literal["text"] = "text"
    text: str


class MediaRefUserInputPart(BaseModel):
    """Reference to a stored blob (tenant-scoped opaque ref)."""

    model_config = {"extra": "forbid"}

    type: Literal["media_ref"] = "media_ref"
    ref: str
    mime_type: str
    filename: str | None = None


UserInputPart = Annotated[
    Union[TextUserInputPart, MediaRefUserInputPart],
    Field(discriminator="type"),
]
