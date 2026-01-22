"""Schemas for sync operations."""
import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SyncStatus(str, enum.Enum):
    """Status of a sync operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncRequest(BaseModel):
    """Request to start a sync for an account."""

    account_id: int


class SyncResponse(BaseModel):
    """Response from sync request."""

    task_id: str
    account_id: int
    status: SyncStatus
    message: str


class SyncProgress(BaseModel):
    """Progress update during sync."""

    account_id: int
    status: SyncStatus
    emails_found: int = 0
    emails_processed: int = 0
    receipts_extracted: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
