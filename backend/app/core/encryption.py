"""Encryption utilities for sensitive data like refresh tokens."""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    """Get Fernet instance using the encryption key from settings."""
    settings = get_settings()
    # Derive a valid Fernet key from our encryption key
    key = hashlib.sha256(settings.encryption_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for storage.

    Args:
        plaintext: The token to encrypt

    Returns:
        Base64-encoded encrypted token
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored token.

    Args:
        ciphertext: Base64-encoded encrypted token

    Returns:
        Decrypted plaintext token
    """
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    encrypted = base64.urlsafe_b64decode(ciphertext.encode())
    decrypted = fernet.decrypt(encrypted)
    return decrypted.decode()
