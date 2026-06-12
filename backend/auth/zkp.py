import hashlib
import os
import binascii

def generate_salt() -> str:
    """Generate a random 16-byte salt, returned as hex."""
    return binascii.hexlify(os.urandom(16)).decode('utf-8')

def create_commitment(value: str | int | float, salt: str) -> str:
    """
    Create a commitment hash for a value using SHA-256.
    commitment = SHA256(str(value) + salt)
    """
    data = f"{value}{salt}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def verify_commitment(value: str | int | float, salt: str, commitment: str) -> bool:
    """
    Verify if the value and salt match the given commitment.
    """
    expected = create_commitment(value, salt)
    return expected == commitment
