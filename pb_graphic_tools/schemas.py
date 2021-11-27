"""Pydantic's models."""
from pydantic import BaseModel
from typing import Optional


class TinyInput(BaseModel):
    size: int
    type: str


class TinyOutput(TinyInput):
    width: int
    height: int
    ratio: float
    url: str


class TinyResponse(BaseModel):
    input: Optional[TinyInput]
    output: Optional[TinyOutput]
    error: Optional[str]
