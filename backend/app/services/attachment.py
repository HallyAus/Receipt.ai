"""Attachment service for download and deduplication."""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.attachment import Attachment
from app.models.email import Email

logger = logging.getLogger(__name__)
settings = get_settings()


class AttachmentService:
    """Handle attachment storage with SHA256 deduplication."""

    def __init__(self, session: Session):
        """Initialize attachment service.

        Args:
            session: Database session
        """
        self.session = session
        self.storage_path = Path(settings.attachment_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_hash(data: bytes) -> str:
        """Compute SHA256 hash of file data.

        Args:
            data: File content as bytes

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(data).hexdigest()

    def _get_storage_path(self, sha256_hash: str, filename: str) -> str:
        """Get storage path for an attachment.

        Uses hash-based directory structure for efficiency:
        attachments/ab/cd/abcdef123456...

        Args:
            sha256_hash: SHA256 hash of the file
            filename: Original filename

        Returns:
            Relative storage path
        """
        # Extract extension from original filename
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ""

        # Create hash-based directory structure
        dir1 = sha256_hash[:2]
        dir2 = sha256_hash[2:4]

        return f"{dir1}/{dir2}/{sha256_hash}{ext}"

    def store_attachment(
        self,
        email_id: int,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Tuple[Optional[Attachment], bool]:
        """Store an attachment with deduplication.

        Args:
            email_id: ID of the parent email
            filename: Original filename
            content_type: MIME type
            data: File content as bytes

        Returns:
            Tuple of (Attachment object, was_new) where was_new is True if
            this is a new unique file, False if deduplicated
        """
        sha256_hash = self.compute_hash(data)
        size_bytes = len(data)

        # Check if attachment with this hash already exists
        existing = self.session.execute(
            select(Attachment).where(Attachment.sha256_hash == sha256_hash)
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Deduplicated attachment {filename} (hash: {sha256_hash[:8]}...)")
            # Link this email to the existing attachment by creating a new record
            # pointing to the same storage path
            storage_path = existing.storage_path
            was_new = False
        else:
            # New unique file - store it
            storage_path = self._get_storage_path(sha256_hash, filename)
            full_path = self.storage_path / storage_path

            # Create directory structure
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(full_path, "wb") as f:
                f.write(data)

            logger.info(f"Stored new attachment {filename} (hash: {sha256_hash[:8]}...)")
            was_new = True

        # Insert attachment record (may conflict on hash)
        try:
            attachment = Attachment(
                email_id=email_id,
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256_hash=sha256_hash,
                storage_path=storage_path,
            )
            self.session.add(attachment)
            self.session.commit()
            return attachment, was_new
        except Exception as e:
            self.session.rollback()
            # Hash conflict - attachment already stored for another email
            # This is expected in deduplication scenario
            logger.debug(f"Attachment hash already exists: {sha256_hash[:8]}...")
            return existing, False

    def get_attachment_path(self, attachment: Attachment) -> Path:
        """Get full filesystem path to an attachment.

        Args:
            attachment: Attachment object

        Returns:
            Full path to the file
        """
        return self.storage_path / attachment.storage_path

    def get_attachment_data(self, attachment: Attachment) -> bytes:
        """Read attachment data from storage.

        Args:
            attachment: Attachment object

        Returns:
            File content as bytes
        """
        path = self.get_attachment_path(attachment)
        with open(path, "rb") as f:
            return f.read()

    def delete_attachment(self, attachment: Attachment) -> bool:
        """Delete an attachment if no other references exist.

        Args:
            attachment: Attachment to delete

        Returns:
            True if file was deleted, False if still referenced
        """
        # Check if other attachments reference the same hash
        count = self.session.execute(
            select(Attachment).where(
                Attachment.sha256_hash == attachment.sha256_hash,
                Attachment.id != attachment.id,
            )
        ).scalar_one_or_none()

        # Delete the database record
        self.session.delete(attachment)
        self.session.commit()

        # Only delete file if no other references
        if count is None:
            path = self.get_attachment_path(attachment)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted attachment file: {attachment.sha256_hash[:8]}...")
                return True

        return False
