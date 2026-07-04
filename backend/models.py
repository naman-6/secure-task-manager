"""
models.py
SQLAlchemy ORM models for the Secure Task & Asset Manager.
"""

import enum
import uuid

from sqlalchemy import Column, String, Text, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Task(Base):
    """
    Represents a single Task / Asset record.
    """

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    asset_tag = Column(String(100), nullable=True, index=True)
    status = Column(
        Enum(TaskStatus, name="task_status_enum"),
        nullable=False,
        default=TaskStatus.PENDING,
    )
    priority = Column(
        Enum(TaskPriority, name="task_priority_enum"),
        nullable=False,
        default=TaskPriority.MEDIUM,
    )
    owner = Column(String(150), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
