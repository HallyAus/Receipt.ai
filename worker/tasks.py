"""Celery tasks for email sync and receipt extraction."""
import logging
from datetime import datetime

from celery import shared_task
from sqlalchemy import select

from app.core.database import SyncSessionLocal
from app.models.account import MailAccount, MailProvider
from app.models.email import Email
from app.services.attachment import AttachmentService
from app.services.extraction import ExtractionService
from app.services.sync_gmail import GmailSyncService
from app.services.sync_microsoft import MicrosoftSyncService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_account_task(self, account_id: int) -> dict:
    """Sync emails for a single account.

    Args:
        account_id: ID of the mail account to sync

    Returns:
        Dict with sync results
    """
    logger.info(f"Starting sync for account {account_id}")

    session = SyncSessionLocal()
    try:
        # Get account
        account = session.execute(
            select(MailAccount).where(MailAccount.id == account_id)
        ).scalar_one_or_none()

        if not account:
            logger.error(f"Account {account_id} not found")
            return {"error": "Account not found"}

        # Create appropriate sync service
        if account.provider == MailProvider.GMAIL:
            sync_service = GmailSyncService(account, session)
        elif account.provider == MailProvider.MICROSOFT:
            sync_service = MicrosoftSyncService(account, session)
        else:
            return {"error": f"Unknown provider: {account.provider}"}

        # Perform sync
        emails_found, emails_inserted = sync_service.sync()

        logger.info(
            f"Sync completed for account {account_id}: "
            f"{emails_found} found, {emails_inserted} inserted"
        )

        # Process unprocessed emails
        receipts_extracted = process_unprocessed_emails(account_id, session, sync_service)

        return {
            "account_id": account_id,
            "emails_found": emails_found,
            "emails_inserted": emails_inserted,
            "receipts_extracted": receipts_extracted,
        }

    except Exception as e:
        logger.error(f"Sync failed for account {account_id}: {e}")
        # Update account with error
        if account:
            account.sync_error = str(e)
            session.commit()
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

    finally:
        session.close()


def process_unprocessed_emails(account_id: int, session, sync_service) -> int:
    """Process unprocessed emails: download attachments and extract receipts.

    Args:
        account_id: Account ID
        session: Database session
        sync_service: Sync service instance

    Returns:
        Number of receipts extracted
    """
    logger.info(f"Processing unprocessed emails for account {account_id}")

    # Get unprocessed emails
    emails = session.execute(
        select(Email).where(
            Email.account_id == account_id,
            Email.processed == 0,
        )
    ).scalars().all()

    attachment_service = AttachmentService(session)
    extraction_service = ExtractionService(session)
    receipts_extracted = 0

    for email in emails:
        try:
            # Download attachments
            attachments = sync_service.get_message_attachments(email.message_id)

            for att in attachments:
                attachment_service.store_attachment(
                    email_id=email.id,
                    filename=att["filename"],
                    content_type=att["mimeType"],
                    data=att["data"],
                )

            # Extract receipt data
            receipt = extraction_service.extract_from_email(email)
            if receipt:
                receipts_extracted += 1
                logger.info(f"Extracted receipt from email {email.id}: {receipt.vendor_name}")

        except Exception as e:
            logger.error(f"Failed to process email {email.id}: {e}")
            email.processed = 2  # Mark as failed/no receipt
            session.commit()

    return receipts_extracted


@shared_task
def sync_all_accounts_task() -> dict:
    """Sync all connected accounts - called periodically.

    Returns:
        Dict with results for each account
    """
    logger.info("Starting sync for all accounts")

    session = SyncSessionLocal()
    try:
        accounts = session.execute(select(MailAccount)).scalars().all()

        results = []
        for account in accounts:
            # Queue individual sync task
            task = sync_account_task.delay(account.id)
            results.append({
                "account_id": account.id,
                "email": account.email,
                "task_id": task.id,
            })

        logger.info(f"Queued sync for {len(results)} accounts")
        return {"accounts_queued": len(results), "tasks": results}

    finally:
        session.close()


@shared_task
def extract_receipt_task(email_id: int) -> dict:
    """Extract receipt from a specific email.

    Args:
        email_id: ID of the email to process

    Returns:
        Dict with extraction results
    """
    logger.info(f"Extracting receipt from email {email_id}")

    session = SyncSessionLocal()
    try:
        email = session.execute(
            select(Email).where(Email.id == email_id)
        ).scalar_one_or_none()

        if not email:
            return {"error": "Email not found"}

        extraction_service = ExtractionService(session)
        receipt = extraction_service.extract_from_email(email)

        if receipt:
            return {
                "email_id": email_id,
                "receipt_id": receipt.id,
                "vendor": receipt.vendor_name,
                "amount": str(receipt.total_amount) if receipt.total_amount else None,
            }
        else:
            return {"email_id": email_id, "receipt_id": None, "message": "No receipt extracted"}

    finally:
        session.close()
