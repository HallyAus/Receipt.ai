"""Gmail sync service with incremental sync using historyId."""
import base64
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.account import MailAccount
from app.models.email import Email
from app.services.oauth_google import GoogleOAuthService

logger = logging.getLogger(__name__)

# Receipt-related labels and queries
RECEIPT_QUERY = "has:attachment (receipt OR invoice OR order OR payment OR purchase OR confirmation)"


class GmailSyncService:
    """Sync emails from Gmail with incremental updates."""

    def __init__(self, account: MailAccount, session: Session):
        """Initialize sync service.

        Args:
            account: The mail account to sync
            session: Database session
        """
        self.account = account
        self.session = session
        self._service = None

    def _get_service(self):
        """Get authenticated Gmail API service, refreshing token if needed."""
        if self._service:
            return self._service

        # Check if token needs refresh
        if self.account.token_expires_at and datetime.utcnow() >= self.account.token_expires_at:
            logger.info(f"Refreshing expired token for account {self.account.id}")
            new_token, new_expires = GoogleOAuthService.refresh_access_token(
                self.account.refresh_token
            )
            self.account.access_token = new_token
            self.account.token_expires_at = new_expires
            self.session.commit()

        self._service = GoogleOAuthService.get_gmail_service(
            self.account.access_token,
            self.account.refresh_token,
        )
        return self._service

    def sync(self) -> Tuple[int, int]:
        """Perform incremental sync of emails.

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        service = self._get_service()
        emails_found = 0
        emails_inserted = 0

        try:
            if self.account.sync_cursor:
                # Incremental sync using history API
                emails_found, emails_inserted = self._incremental_sync(service)
            else:
                # Initial sync - get recent emails
                emails_found, emails_inserted = self._initial_sync(service)

            # Update sync status
            self.account.last_sync_at = datetime.utcnow()
            self.account.sync_error = None
            self.session.commit()

        except Exception as e:
            logger.error(f"Sync failed for account {self.account.id}: {e}")
            self.account.sync_error = str(e)
            self.session.commit()
            raise

        return emails_found, emails_inserted

    def _initial_sync(self, service) -> Tuple[int, int]:
        """Perform initial sync - fetch recent receipt-like emails.

        Args:
            service: Gmail API service

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        logger.info(f"Performing initial sync for account {self.account.id}")

        emails_found = 0
        emails_inserted = 0
        page_token = None

        # Get profile to establish initial historyId
        profile = service.users().getProfile(userId="me").execute()
        latest_history_id = profile.get("historyId")

        while True:
            # Search for receipt-like emails
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=RECEIPT_QUERY,
                    maxResults=100,
                    pageToken=page_token,
                )
                .execute()
            )

            messages = results.get("messages", [])
            emails_found += len(messages)

            for msg in messages:
                inserted = self._process_message(service, msg["id"])
                if inserted:
                    emails_inserted += 1

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        # Store the historyId as sync cursor
        self.account.sync_cursor = latest_history_id
        return emails_found, emails_inserted

    def _incremental_sync(self, service) -> Tuple[int, int]:
        """Perform incremental sync using Gmail history API.

        Args:
            service: Gmail API service

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        logger.info(f"Performing incremental sync for account {self.account.id} from history {self.account.sync_cursor}")

        emails_found = 0
        emails_inserted = 0
        page_token = None
        latest_history_id = self.account.sync_cursor

        try:
            while True:
                history = (
                    service.users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=self.account.sync_cursor,
                        historyTypes=["messageAdded"],
                        pageToken=page_token,
                    )
                    .execute()
                )

                # Update to latest history ID
                if "historyId" in history:
                    latest_history_id = history["historyId"]

                # Process new messages
                for record in history.get("history", []):
                    for msg_added in record.get("messagesAdded", []):
                        msg = msg_added.get("message", {})
                        msg_id = msg.get("id")
                        if msg_id:
                            emails_found += 1
                            # Check if message matches receipt criteria
                            if self._is_receipt_candidate(service, msg_id):
                                inserted = self._process_message(service, msg_id)
                                if inserted:
                                    emails_inserted += 1

                page_token = history.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            if "404" in str(e) or "historyId" in str(e).lower():
                # History expired, need to do a full re-sync
                logger.warning(f"History expired for account {self.account.id}, doing full resync")
                self.account.sync_cursor = None
                return self._initial_sync(service)
            raise

        # Update sync cursor
        self.account.sync_cursor = latest_history_id
        return emails_found, emails_inserted

    def _is_receipt_candidate(self, service, message_id: str) -> bool:
        """Check if a message might be a receipt.

        Args:
            service: Gmail API service
            message_id: Message ID to check

        Returns:
            True if message might be a receipt
        """
        # Get message metadata only
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Subject", "From"])
            .execute()
        )

        # Check for attachments
        payload = msg.get("payload", {})
        if not payload.get("parts"):
            return False

        has_attachment = any(
            part.get("filename") and part.get("body", {}).get("attachmentId")
            for part in payload.get("parts", [])
        )

        if not has_attachment:
            return False

        # Check subject for receipt-related keywords
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        subject = headers.get("subject", "").lower()
        receipt_keywords = ["receipt", "invoice", "order", "payment", "purchase", "confirmation", "transaction"]

        return any(keyword in subject for keyword in receipt_keywords)

    def _process_message(self, service, message_id: str) -> bool:
        """Process a single message and insert into database.

        Args:
            service: Gmail API service
            message_id: Message ID to process

        Returns:
            True if message was inserted, False if already exists
        """
        # Get full message
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()

        # Extract headers
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        subject = headers.get("subject")
        sender = headers.get("from")

        # Parse date
        received_at = None
        if "date" in headers:
            try:
                from email.utils import parsedate_to_datetime

                received_at = parsedate_to_datetime(headers["date"]).replace(tzinfo=None)
            except Exception:
                pass

        # Get body snippet
        body_snippet = msg.get("snippet", "")[:500]

        # Idempotent insert using ON CONFLICT DO NOTHING
        stmt = insert(Email).values(
            account_id=self.account.id,
            message_id=message_id,
            subject=subject,
            sender=sender,
            received_at=received_at,
            body_snippet=body_snippet,
            processed=0,
        ).on_conflict_do_nothing(
            index_elements=["account_id", "message_id"]
        )

        result = self.session.execute(stmt)
        self.session.commit()

        # Return True if a row was inserted
        return result.rowcount > 0

    def get_message_attachments(self, message_id: str) -> List[dict]:
        """Get attachments for a message.

        Args:
            message_id: Message ID

        Returns:
            List of attachment info dicts with 'id', 'filename', 'mimeType', 'data'
        """
        service = self._get_service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()

        attachments = []
        payload = msg.get("payload", {})

        def process_parts(parts):
            for part in parts:
                if part.get("filename") and part.get("body", {}).get("attachmentId"):
                    mime_type = part.get("mimeType", "").lower()
                    if mime_type in ["application/pdf", "image/png", "image/jpeg", "image/jpg"]:
                        # Get attachment data
                        att_id = part["body"]["attachmentId"]
                        attachment = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=message_id, id=att_id)
                            .execute()
                        )

                        attachments.append({
                            "id": att_id,
                            "filename": part["filename"],
                            "mimeType": mime_type,
                            "data": base64.urlsafe_b64decode(attachment["data"]),
                            "size": attachment.get("size", 0),
                        })

                # Recurse into nested parts
                if part.get("parts"):
                    process_parts(part["parts"])

        if payload.get("parts"):
            process_parts(payload["parts"])

        return attachments
