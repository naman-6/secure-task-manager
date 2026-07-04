"""
schemas.py
Pydantic models used for request validation and response serialization.
Keeping these separate from the SQLAlchemy models (models.py) enforces a
clean boundary between the DB layer and the API contract.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Short task title")
    description: Optional[str] = Field(None, max_length=5000)
    asset_tag: Optional[str] = Field(
        None, max_length=100, description="Optional inventory / asset tag reference"
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    owner: str = Field(..., min_length=1, max_length=150)

    @field_validator("title", "owner")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return stripped

    @field_validator("asset_tag")
    @classmethod
    def normalize_asset_tag(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None


class TaskCreate(TaskBase):
    """Payload for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """
    Payload for updating an existing task. All fields optional to support
    partial (PATCH-style) updates via the same endpoint.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    asset_tag: Optional[str] = Field(None, max_length=100)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    owner: Optional[str] = Field(None, min_length=1, max_length=150)

    @field_validator("title", "owner")
    @classmethod
    def strip_and_reject_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return stripped


class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
