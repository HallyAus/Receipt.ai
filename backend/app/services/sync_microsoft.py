"""Microsoft Graph sync service with delta queries."""
import base64
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.account import MailAccount
from app.models.email import Email
from app.services.oauth_microsoft import MicrosoftOAuthService

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Receipt-related search filter
RECEIPT_FILTER = "hasAttachments eq true"
RECEIPT_SEARCH = "receipt OR invoice OR order OR payment OR purchase OR confirmation"


class MicrosoftSyncService:
    """Sync emails from Microsoft 365 with delta queries."""

    def __init__(self, account: MailAccount, session: Session):
        """Initialize sync service.

        Args:
            account: The mail account to sync
            session: Database session
        """
        self.account = account
        self.session = session
        self._access_token = None

    def _get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        if self._access_token:
            return self._access_token

        # Check if token needs refresh
        if self.account.token_expires_at and datetime.utcnow() >= self.account.token_expires_at:
            logger.info(f"Refreshing expired token for account {self.account.id}")
            new_token, new_refresh, new_expires = MicrosoftOAuthService.refresh_access_token(
                self.account.refresh_token
            )
            self.account.access_token = new_token
            self.account.refresh_token = new_refresh
            self.account.token_expires_at = new_expires
            self.session.commit()

        self._access_token = self.account.access_token
        return self._access_token

    def _get_headers(self) -> dict:
        """Get headers for Graph API requests."""
        return MicrosoftOAuthService.get_graph_headers(self._get_access_token())

    def sync(self) -> Tuple[int, int]:
        """Perform incremental sync of emails using delta queries.

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        emails_found = 0
        emails_inserted = 0

        try:
            if self.account.sync_cursor:
                # Use delta link for incremental sync
                emails_found, emails_inserted = self._delta_sync()
            else:
                # Initial sync
                emails_found, emails_inserted = self._initial_sync()

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

    def _initial_sync(self) -> Tuple[int, int]:
        """Perform initial sync - establish delta link and fetch receipt emails.

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        logger.info(f"Performing initial sync for account {self.account.id}")

        emails_found = 0
        emails_inserted = 0

        with httpx.Client(timeout=30.0) as client:
            # Start delta query to establish tracking
            # We use delta query on messages to get initial set and deltaLink
            url = f"{GRAPH_BASE}/me/mailFolders/inbox/messages/delta"
            params = {
                "$select": "id,subject,from,receivedDateTime,bodyPreview,hasAttachments",
                "$filter": RECEIPT_FILTER,
                "$top": "100",
            }

            while url:
                response = client.get(url, headers=self._get_headers(), params=params if "delta" in url else None)

                if response.status_code == 401:
                    # Token expired mid-request, refresh and retry
                    self._access_token = None
                    self.account.token_expires_at = datetime.utcnow()
                    response = client.get(url, headers=self._get_headers(), params=params if "delta" in url else None)

                response.raise_for_status()
                data = response.json()

                # Process messages
                for msg in data.get("value", []):
                    if self._is_receipt_candidate(msg):
                        emails_found += 1
                        inserted = self._process_message(msg)
                        if inserted:
                            emails_inserted += 1

                # Check for next page or delta link
                if "@odata.nextLink" in data:
                    url = data["@odata.nextLink"]
                    params = None  # nextLink includes params
                elif "@odata.deltaLink" in data:
                    # Store delta link as sync cursor
                    self.account.sync_cursor = data["@odata.deltaLink"]
                    url = None
                else:
                    url = None

        return emails_found, emails_inserted

    def _delta_sync(self) -> Tuple[int, int]:
        """Perform incremental sync using stored delta link.

        Returns:
            Tuple of (emails_found, emails_inserted)
        """
        logger.info(f"Performing delta sync for account {self.account.id}")

        emails_found = 0
        emails_inserted = 0

        with httpx.Client(timeout=30.0) as client:
            url = self.account.sync_cursor

            while url:
                try:
                    response = client.get(url, headers=self._get_headers())

                    if response.status_code == 401:
                        self._access_token = None
                        self.account.token_expires_at = datetime.utcnow()
                        response = client.get(url, headers=self._get_headers())

                    if response.status_code == 410:
                        # Delta link expired, need full resync
                        logger.warning(f"Delta link expired for account {self.account.id}, doing full resync")
                        self.account.sync_cursor = None
                        return self._initial_sync()

                    response.raise_for_status()
                    data = response.json()

                    # Process messages (including changes and new)
                    for msg in data.get("value", []):
                        # Skip deleted messages
                        if "@removed" in msg:
                            continue

                        if self._is_receipt_candidate(msg):
                            emails_found += 1
                            inserted = self._process_message(msg)
                            if inserted:
                                emails_inserted += 1

                    # Check for next page or new delta link
                    if "@odata.nextLink" in data:
                        url = data["@odata.nextLink"]
                    elif "@odata.deltaLink" in data:
                        self.account.sync_cursor = data["@odata.deltaLink"]
                        url = None
                    else:
                        url = None

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 410:
                        logger.warning(f"Delta link expired for account {self.account.id}")
                        self.account.sync_cursor = None
                        return self._initial_sync()
                    raise

        return emails_found, emails_inserted

    def _is_receipt_candidate(self, msg: dict) -> bool:
        """Check if a message might be a receipt.

        Args:
            msg: Message object from Graph API

        Returns:
            True if message might be a receipt
        """
        if not msg.get("hasAttachments"):
            return False

        # Check subject for receipt-related keywords
        subject = (msg.get("subject") or "").lower()
        body_preview = (msg.get("bodyPreview") or "").lower()
        receipt_keywords = ["receipt", "invoice", "order", "payment", "purchase", "confirmation", "transaction"]

        return any(keyword in subject or keyword in body_preview for keyword in receipt_keywords)

    def _process_message(self, msg: dict) -> bool:
        """Process a single message and insert into database.

        Args:
            msg: Message object from Graph API

        Returns:
            True if message was inserted, False if already exists
        """
        message_id = msg.get("id")
        subject = msg.get("subject")

        # Extract sender
        sender = None
        from_field = msg.get("from", {}).get("emailAddress", {})
        if from_field:
            sender = from_field.get("address") or from_field.get("name")

        # Parse date
        received_at = None
        if msg.get("receivedDateTime"):
            try:
                received_at = datetime.fromisoformat(msg["receivedDateTime"].replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

        # Get body snippet
        body_snippet = (msg.get("bodyPreview") or "")[:500]

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

        return result.rowcount > 0

    def get_message_attachments(self, message_id: str) -> List[dict]:
        """Get attachments for a message.

        Args:
            message_id: Message ID

        Returns:
            List of attachment info dicts with 'id', 'filename', 'mimeType', 'data'
        """
        attachments = []

        with httpx.Client(timeout=30.0) as client:
            # List attachments
            url = f"{GRAPH_BASE}/me/messages/{message_id}/attachments"
            response = client.get(url, headers=self._get_headers())
            response.raise_for_status()

            for att in response.json().get("value", []):
                # Only process file attachments with supported types
                if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                    continue

                content_type = (att.get("contentType") or "").lower()
                if content_type not in ["application/pdf", "image/png", "image/jpeg", "image/jpg"]:
                    continue

                # Attachment data is base64 encoded
                data = base64.b64decode(att.get("contentBytes", ""))

                attachments.append({
                    "id": att.get("id"),
                    "filename": att.get("name"),
                    "mimeType": content_type,
                    "data": data,
                    "size": att.get("size", len(data)),
                })

        return attachments
