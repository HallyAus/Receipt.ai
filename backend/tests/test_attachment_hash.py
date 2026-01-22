"""Tests for attachment hash stability and deduplication."""
import hashlib
import os
import tempfile
import pytest

from app.services.attachment import AttachmentService


class TestAttachmentHashStability:
    """Test that attachment hashing is stable and consistent."""

    def test_hash_is_deterministic(self):
        """Same content should always produce same hash."""
        content = b"This is a test receipt PDF content"

        hash1 = AttachmentService.compute_hash(content)
        hash2 = AttachmentService.compute_hash(content)
        hash3 = AttachmentService.compute_hash(content)

        assert hash1 == hash2 == hash3

    def test_hash_is_sha256(self):
        """Hash should be a valid SHA256 hex string."""
        content = b"Test content"
        computed_hash = AttachmentService.compute_hash(content)

        # SHA256 produces 64 hex characters
        assert len(computed_hash) == 64
        assert all(c in '0123456789abcdef' for c in computed_hash)

        # Verify it matches Python's hashlib
        expected = hashlib.sha256(content).hexdigest()
        assert computed_hash == expected

    def test_different_content_different_hash(self):
        """Different content should produce different hashes."""
        content1 = b"Receipt from Amazon"
        content2 = b"Receipt from Amazon "  # Note: trailing space

        hash1 = AttachmentService.compute_hash(content1)
        hash2 = AttachmentService.compute_hash(content2)

        assert hash1 != hash2

    def test_empty_content_hash(self):
        """Empty content should have a valid hash."""
        content = b""
        computed_hash = AttachmentService.compute_hash(content)

        # SHA256 of empty string
        expected = hashlib.sha256(b"").hexdigest()
        assert computed_hash == expected
        assert len(computed_hash) == 64

    def test_large_file_hash(self):
        """Large files should be hashed correctly."""
        # Create 10MB of content
        content = b"x" * (10 * 1024 * 1024)
        computed_hash = AttachmentService.compute_hash(content)

        expected = hashlib.sha256(content).hexdigest()
        assert computed_hash == expected

    def test_binary_pdf_hash(self):
        """Binary PDF-like content should hash correctly."""
        # Simulate PDF header
        content = b"%PDF-1.4\n" + b"\x00" * 100 + b"receipt data"
        computed_hash = AttachmentService.compute_hash(content)

        assert len(computed_hash) == 64
        # Verify consistency
        assert computed_hash == AttachmentService.compute_hash(content)


class TestStoragePathGeneration:
    """Test that storage paths are generated correctly."""

    def test_storage_path_structure(self, sync_session):
        """Storage path should use hash-based directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock the storage path
            original_path = os.environ.get("ATTACHMENT_STORAGE_PATH", "")
            os.environ["ATTACHMENT_STORAGE_PATH"] = tmpdir

            try:
                service = AttachmentService(sync_session)
                content = b"Test receipt content"
                sha256_hash = AttachmentService.compute_hash(content)

                path = service._get_storage_path(sha256_hash, "receipt.pdf")

                # Should be structured as ab/cd/abcdef...pdf
                parts = path.split("/")
                assert len(parts) == 3
                assert parts[0] == sha256_hash[:2]
                assert parts[1] == sha256_hash[2:4]
                assert parts[2].startswith(sha256_hash)
                assert parts[2].endswith(".pdf")

            finally:
                os.environ["ATTACHMENT_STORAGE_PATH"] = original_path

    def test_extension_preserved(self, sync_session):
        """File extension should be preserved in storage path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = os.environ.get("ATTACHMENT_STORAGE_PATH", "")
            os.environ["ATTACHMENT_STORAGE_PATH"] = tmpdir

            try:
                service = AttachmentService(sync_session)
                sha256_hash = "a" * 64

                # Test different extensions
                pdf_path = service._get_storage_path(sha256_hash, "receipt.pdf")
                png_path = service._get_storage_path(sha256_hash, "image.png")
                jpg_path = service._get_storage_path(sha256_hash, "photo.JPG")

                assert pdf_path.endswith(".pdf")
                assert png_path.endswith(".png")
                assert jpg_path.endswith(".jpg")

            finally:
                os.environ["ATTACHMENT_STORAGE_PATH"] = original_path
