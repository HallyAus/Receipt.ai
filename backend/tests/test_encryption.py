"""Tests for token encryption."""
import pytest

from app.core.encryption import encrypt_token, decrypt_token


class TestTokenEncryption:
    """Test that token encryption works correctly."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted token should decrypt to original."""
        original = "my-super-secret-refresh-token-12345"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original

    def test_encrypted_differs_from_original(self):
        """Encrypted token should not equal original."""
        original = "my-secret-token"
        encrypted = encrypt_token(original)

        assert encrypted != original

    def test_encrypted_is_base64(self):
        """Encrypted token should be valid base64."""
        original = "test-token"
        encrypted = encrypt_token(original)

        # Should not raise
        import base64
        base64.urlsafe_b64decode(encrypted)

    def test_empty_token(self):
        """Empty token should return empty string."""
        assert encrypt_token("") == ""
        assert decrypt_token("") == ""

    def test_different_tokens_different_ciphertext(self):
        """Different tokens should produce different ciphertext."""
        token1 = "token-1"
        token2 = "token-2"

        encrypted1 = encrypt_token(token1)
        encrypted2 = encrypt_token(token2)

        assert encrypted1 != encrypted2

    def test_unicode_token(self):
        """Unicode tokens should be handled correctly."""
        original = "token-with-unicode-αβγ-日本語"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original

    def test_long_token(self):
        """Long tokens should be handled correctly."""
        original = "x" * 10000  # 10KB token
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original

    def test_special_characters(self):
        """Tokens with special characters should work."""
        original = "token+with/special=chars&more!"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original
