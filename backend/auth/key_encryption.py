"""
Key Encryption Utility
======================
Provides transparent Fernet-based symmetric encryption for ECDSA private keys
stored in the database.

Why Fernet:
  • AES-128-CBC + HMAC-SHA256 under the hood — auditable, not exotic
  • Built into `cryptography` (already a project dependency)
  • Deterministically reversible (needed for signing operations)
  • One master key (KEY_ENCRYPTION_SECRET) encrypts all entity private keys
    → compromise of a single DB row reveals one PEM, not the master key

Usage:
  from auth.key_encryption import encrypt_private_key, decrypt_private_key

  # On registration: store encrypted
  encrypted = encrypt_private_key(raw_pem)

  # On signing: recover raw PEM
  raw_pem = decrypt_private_key(encrypted)
"""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Lazy-loaded fernet instance (avoids import-time circular deps with config)
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        from config import settings  # deferred import
        raw = settings.KEY_ENCRYPTION_SECRET
        if not raw:
            raise RuntimeError(
                "KEY_ENCRYPTION_SECRET is not set in environment. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        # Accept either a raw Fernet key (44-char base64) or a hex secret we
        # derive a Fernet key from by base64-encoding the first 32 bytes.
        try:
            _fernet = Fernet(raw.encode() if isinstance(raw, str) else raw)
        except Exception:
            # Treat it as a raw hex/bytes secret → derive a valid Fernet key
            import hashlib
            derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
            _fernet = Fernet(derived)
    return _fernet


# ── Public API ────────────────────────────────────────────────────────────────

def encrypt_private_key(raw_pem: Optional[str]) -> Optional[str]:
    """
    Encrypt a PEM private key string.
    Returns an 'enc:' prefixed ciphertext string, or None if input is None.
    The prefix lets us distinguish already-encrypted from plaintext values
    in the migration script.
    """
    if raw_pem is None:
        return None
    fernet = _get_fernet()
    ciphertext = fernet.encrypt(raw_pem.encode())
    return "enc:" + base64.urlsafe_b64encode(ciphertext).decode()


def decrypt_private_key(stored: Optional[str]) -> Optional[str]:
    """
    Decrypt a stored private key. Handles three cases transparently:
      1. None → returns None
      2. Starts with 'enc:' → Fernet decrypt
      3. Plain PEM (legacy row before migration) → return as-is with a warning
         so existing functionality isn't broken while migration is in progress
    """
    if stored is None:
        return None
    if not stored.startswith("enc:"):
        # Legacy plaintext — still works but should be migrated
        logger.warning(
            "Private key is stored as plaintext. Run `python scripts/migrate_encrypt_keys.py` "
            "to encrypt all existing keys."
        )
        return stored
    try:
        fernet = _get_fernet()
        raw_bytes = base64.urlsafe_b64decode(stored[4:].encode())
        return fernet.decrypt(raw_bytes).decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt private key — wrong KEY_ENCRYPTION_SECRET or corrupted data."
        )
        raise RuntimeError(
            "Private key decryption failed. Check KEY_ENCRYPTION_SECRET in your environment."
        )


def is_encrypted(stored: Optional[str]) -> bool:
    """Check whether a stored key value is already encrypted."""
    return stored is not None and stored.startswith("enc:")
