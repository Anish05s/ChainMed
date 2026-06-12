from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import base64, json


def generate_entity_keypair() -> dict:
    """Generate secp256k1 keypair for an entity on registration."""
    private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
    public_key = private_key.public_key()
    return {
        "private_key_pem": private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).decode(),
        "public_key_pem": public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
    }


def sign_handoff(private_key_pem: str, handoff_data: dict) -> str:
    """Entity signs their handoff submission. Returns base64 signature."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None, backend=default_backend()
    )
    payload = json.dumps(handoff_data, sort_keys=True).encode()
    signature = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode()


def verify_handoff_signature(public_key_pem: str, handoff_data: dict, signature_b64: str) -> bool:
    """Verify a party's signature on their handoff data. Returns True if valid."""
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), backend=default_backend()
        )
        payload = json.dumps(handoff_data, sort_keys=True).encode()
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
