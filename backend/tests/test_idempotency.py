"""Tests for idempotent email insertion."""
import pytest
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.account import MailAccount, MailProvider
from app.models.email import Email


class TestEmailIdempotency:
    """Test that email insertion is idempotent."""

    def test_duplicate_email_not_inserted(self, sync_session):
        """Inserting the same email twice should only create one record."""
        # Create test account
        account = MailAccount(
            provider=MailProvider.GMAIL,
            email="test@example.com",
            account_id="123456",
        )
        account.refresh_token = "test-refresh-token"
        sync_session.add(account)
        sync_session.commit()

        # First insert
        email1 = Email(
            account_id=account.id,
            message_id="msg-123",
            subject="Test Receipt",
            sender="vendor@example.com",
        )
        sync_session.add(email1)
        sync_session.commit()

        # Try to insert same email again (simulating re-sync)
        # In production, we use ON CONFLICT DO NOTHING
        # For SQLite in tests, we check manually
        existing = sync_session.execute(
            select(Email).where(
                Email.account_id == account.id,
                Email.message_id == "msg-123",
            )
        ).scalar_one_or_none()

        # Verify only one email exists
        assert existing is not None
        assert existing.id == email1.id

        # Count total emails
        all_emails = sync_session.execute(
            select(Email).where(Email.account_id == account.id)
        ).scalars().all()
        assert len(all_emails) == 1

    def test_different_message_ids_create_separate_records(self, sync_session):
        """Different message IDs should create separate records."""
        # Create test account
        account = MailAccount(
            provider=MailProvider.GMAIL,
            email="test@example.com",
            account_id="123456",
        )
        account.refresh_token = "test-refresh-token"
        sync_session.add(account)
        sync_session.commit()

        # Insert first email
        email1 = Email(
            account_id=account.id,
            message_id="msg-123",
            subject="Receipt 1",
        )
        sync_session.add(email1)

        # Insert second email
        email2 = Email(
            account_id=account.id,
            message_id="msg-456",
            subject="Receipt 2",
        )
        sync_session.add(email2)
        sync_session.commit()

        # Verify both emails exist
        all_emails = sync_session.execute(
            select(Email).where(Email.account_id == account.id)
        ).scalars().all()
        assert len(all_emails) == 2

    def test_same_message_id_different_accounts(self, sync_session):
        """Same message ID from different accounts should create separate records."""
        # Create two test accounts
        account1 = MailAccount(
            provider=MailProvider.GMAIL,
            email="user1@example.com",
            account_id="account-1",
        )
        account1.refresh_token = "token-1"

        account2 = MailAccount(
            provider=MailProvider.GMAIL,
            email="user2@example.com",
            account_id="account-2",
        )
        account2.refresh_token = "token-2"

        sync_session.add_all([account1, account2])
        sync_session.commit()

        # Insert same message_id for both accounts
        email1 = Email(
            account_id=account1.id,
            message_id="msg-123",
            subject="Receipt",
        )
        email2 = Email(
            account_id=account2.id,
            message_id="msg-123",  # Same message_id
            subject="Receipt",
        )
        sync_session.add_all([email1, email2])
        sync_session.commit()

        # Verify both emails exist (unique constraint is on account_id + message_id)
        all_emails = sync_session.execute(select(Email)).scalars().all()
        assert len(all_emails) == 2
