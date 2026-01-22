"""Mail account model for OAuth connections."""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.encryption import decrypt_token, encrypt_token


class MailProvider(str, enum.Enum):
    """Supported mail providers."""

    GMAIL = "gmail"
    MICROSOFT = "microsoft"


class MailAccount(Base):
    """Connected mail account with OAuth tokens."""

    __tablename__ = "mail_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(Enum(MailProvider), nullable=False)
    email = Column(String(255), nullable=False)
    account_id = Column(String(255), nullable=False)  # Provider's user ID

    # Encrypted OAuth tokens - NEVER log these
    _access_token_encrypted = Column("access_token", Text, nullable=True)
    _refresh_token_encrypted = Column("refresh_token", Text, nullable=False)

    # Token expiration
    token_expires_at = Column(DateTime, nullable=True)

    # Sync state
    sync_cursor = Column(Text, nullable=True)  # Gmail: historyId, Microsoft: deltaLink
    last_sync_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    emails = relationship("Email", back_populates="account", cascade="all, delete-orphan")

    # Unique constraint: one account per provider+account_id
    __table_args__ = (
        UniqueConstraint("provider", "account_id", name="uq_provider_account"),
    )

    @property
    def access_token(self) -> Optional[str]:
        """Decrypt and return access token."""
        if self._access_token_encrypted:
            return decrypt_token(self._access_token_encrypted)
        return None

    @access_token.setter
    def access_token(self, value: Optional[str]):
        """Encrypt and store access token."""
        if value:
            self._access_token_encrypted = encrypt_token(value)
        else:
            self._access_token_encrypted = None

    @property
    def refresh_token(self) -> Optional[str]:
        """Decrypt and return refresh token."""
        if self._refresh_token_encrypted:
            return decrypt_token(self._refresh_token_encrypted)
        return None

    @refresh_token.setter
    def refresh_token(self, value: str):
        """Encrypt and store refresh token."""
        self._refresh_token_encrypted = encrypt_token(value)

    def __repr__(self) -> str:
        return f"<MailAccount {self.provider.value}:{self.email}>"
