from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TranscriptionCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    text: str = Field(min_length=1)
    language: Optional[str] = Field(default=None, max_length=20)
    duration_seconds: float = Field(default=0.0, ge=0)


class TranscriptionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    text: Optional[str] = None
    language: Optional[str] = Field(default=None, max_length=20)


class TranscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    text: str
    language: Optional[str]
    duration_seconds: float
    created_at: datetime
    updated_at: datetime
