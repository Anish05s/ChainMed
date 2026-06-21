#!/usr/bin/env python3
"""
Migration Script: Encrypt all existing plaintext private keys in the database.

Run ONCE after setting KEY_ENCRYPTION_SECRET in your .env:
    cd backend
    python scripts/migrate_encrypt_keys.py

Safe to re-run — already-encrypted keys (prefixed with 'enc:') are skipped.
"""

import sys
import os

# Add parent dir to path so imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import User, Manufacturer, Supplier, Consumer
from auth.key_encryption import encrypt_private_key, is_encrypted


def migrate_table(db, model, label: str):
    rows = db.query(model).all()
    encrypted_count = 0
    skipped_count = 0

    for row in rows:
        if row.private_key_pem is None:
            skipped_count += 1
            continue
        if is_encrypted(row.private_key_pem):
            skipped_count += 1
            continue
        row.private_key_pem = encrypt_private_key(row.private_key_pem)
        encrypted_count += 1

    print(f"  {label}: {encrypted_count} encrypted, {skipped_count} skipped (already encrypted or null)")
    return encrypted_count


def main():
    print("=" * 60)
    print("PharmaChain — Private Key Encryption Migration")
    print("=" * 60)

    # Validate that KEY_ENCRYPTION_SECRET is set before doing anything
    from config import settings
    if not settings.KEY_ENCRYPTION_SECRET:
        print("\n❌ ERROR: KEY_ENCRYPTION_SECRET is not set in your .env file.")
        print("   Generate one with:")
        print("   python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        sys.exit(1)

    print(f"\n[OK] KEY_ENCRYPTION_SECRET is set (length: {len(settings.KEY_ENCRYPTION_SECRET)} chars)")
    print("\nStarting migration...\n")

    db = SessionLocal()
    total = 0
    try:
        total += migrate_table(db, User, "Users")
        total += migrate_table(db, Manufacturer, "Manufacturers")
        total += migrate_table(db, Supplier, "Suppliers")
        total += migrate_table(db, Consumer, "Consumers")

        db.commit()
        print(f"\n[DONE] Migration complete. {total} private keys encrypted and saved.")
        print("   Keep KEY_ENCRYPTION_SECRET safe -- losing it means losing access to all signing keys.")
    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Migration failed: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
