"""Email model for synced messages."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class Email(Base):
    """Synced email message from mail provider."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("mail_accounts.id", ondelete="CASCADE"), nullable=False)

    # Provider message ID for idempotent sync
    message_id = Column(String(255), nullable=False)

    # Email metadata
    subject = Column(Text, nullable=True)
    sender = Column(String(255), nullable=True)
    received_at = Column(DateTime, nullable=True)

    # For receipt detection heuristics
    body_snippet = Column(Text, nullable=True)  # First ~500 chars for rules

    # Processing state
    processed = Column(Integer, default=0)  # 0=pending, 1=processed, 2=no_receipt

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account = relationship("MailAccount", back_populates="emails")
    attachments = relationship("Attachment", back_populates="email", cascade="all, delete-orphan")
    receipt = relationship("Receipt", back_populates="email", uselist=False, cascade="all, delete-orphan")

    # Unique constraint: provider + account + message_id for idempotent inserts
    __table_args__ = (
        UniqueConstraint("account_id", "message_id", name="uq_account_message"),
    )

    def __repr__(self) -> str:
        return f"<Email {self.id}: {self.subject[:30] if self.subject else 'No subject'}>"
