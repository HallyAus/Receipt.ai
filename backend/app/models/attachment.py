"""Attachment model for email attachments."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class Attachment(Base):
    """Email attachment with deduplication by SHA256 hash."""

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)

    # Original attachment info
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)  # pdf, png, jpg
    size_bytes = Column(Integer, nullable=False)

    # Deduplication
    sha256_hash = Column(String(64), nullable=False, index=True)

    # Storage path (relative to attachment_storage_path)
    storage_path = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    email = relationship("Email", back_populates="attachments")

    # Unique constraint for the hash ensures we don't store duplicates
    __table_args__ = (
        UniqueConstraint("sha256_hash", name="uq_attachment_hash"),
    )

    def __repr__(self) -> str:
        return f"<Attachment {self.filename} ({self.sha256_hash[:8]}...)>"
