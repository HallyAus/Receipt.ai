"""Schemas for mail account operations."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from app.models.account import MailProvider


class AccountCreate(BaseModel):
    """Request to create/connect a mail account."""

    provider: MailProvider
    code: str  # OAuth authorization code


class AccountResponse(BaseModel):
    """Mail account response (never includes tokens)."""

    id: int
    provider: MailProvider
    email: str
    last_sync_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    """List of connected mail accounts."""

    accounts: List[AccountResponse]
    total: int
