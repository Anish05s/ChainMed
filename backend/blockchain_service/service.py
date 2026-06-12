"""
ChainMed Blockchain Service
================================
Handles async interaction with the ChainMed Solidity contract on
Ethereum Sepolia testnet.

MOCK MODE (default when CONTRACT_ADDRESS is empty):
  - Generates a deterministic SHA-256 hash from the payload.
  - Returns "mock:sha256:<hash>" as the tx hash.
  - Indistinguishable in a demo; swap 3 env vars for real Sepolia.

REAL MODE (set ETHEREUM_RPC_URL, ETHEREUM_PRIVATE_KEY, CONTRACT_ADDRESS):
  - Calls recordHandoff() on Sepolia via web3.py.
  - Returns the real tx hash.
  - Non-blocking: called as a BackgroundTask so the API response is instant.
"""

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Try to import web3; gracefully degrade if not installed ─────────────────
try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    _WEB3_AVAILABLE = True
except ImportError:
    _WEB3_AVAILABLE = False
    logger.warning("web3 not available — blockchain service running in mock mode")


# ── Minimal ABI (only the functions we call) ─────────────────────────────────
_CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "shipmentId", "type": "string"},
            {"internalType": "string", "name": "dataHash",   "type": "string"},
            {"internalType": "string", "name": "status",     "type": "string"},
            {"internalType": "uint8",  "name": "riskScore",  "type": "uint8"},
        ],
        "name": "recordHandoff",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "shipmentId", "type": "string"},
            {"internalType": "string", "name": "reason",     "type": "string"},
        ],
        "name": "flagShipment",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "shipmentId", "type": "string"},
        ],
        "name": "getHandoff",
        "outputs": [
            {"internalType": "string",  "name": "dataHash",   "type": "string"},
            {"internalType": "string",  "name": "status",     "type": "string"},
            {"internalType": "uint8",   "name": "riskScore",  "type": "uint8"},
            {"internalType": "uint256", "name": "timestamp",  "type": "uint256"},
            {"internalType": "string",  "name": "flagReason", "type": "string"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "shipmentId", "type": "string"},
        ],
        "name": "handoffExists",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _make_data_hash(shipment_id: str, status: str, risk_score: float) -> str:
    """SHA-256 of the canonical payload — stored on-chain as the data proof."""
    payload = json.dumps(
        {"shipment_id": shipment_id, "status": status, "risk_score": risk_score},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _mock_tx_hash(shipment_id: str, data_hash: str) -> str:
    """Deterministic fake tx hash for demo/dev mode."""
    combined = f"{shipment_id}:{data_hash}"
    h = hashlib.sha256(combined.encode()).hexdigest()
    return f"mock:sha256:{h}"


class BlockchainService:
    """
    Singleton-style service instantiated once at startup.
    Automatically selects mock vs real mode from environment.
    """

    def __init__(self, rpc_url: str, private_key: str, contract_address: str):
        self._mock_mode = not (rpc_url and private_key and contract_address)

        if self._mock_mode:
            logger.info(
                "BlockchainService: running in MOCK MODE. "
                "Set ETHEREUM_RPC_URL, ETHEREUM_PRIVATE_KEY, CONTRACT_ADDRESS "
                "in .env for real Sepolia transactions."
            )
            self._w3 = None
            self._contract = None
            self._account = None
        else:
            if not _WEB3_AVAILABLE:
                logger.error("web3 library not installed but real mode requested. Falling back to mock.")
                self._mock_mode = True
                self._w3 = None
                return

            self._w3 = Web3(Web3.HTTPProvider(rpc_url))
            # Sepolia is PoA-compatible; inject middleware
            self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

            if not self._w3.is_connected():
                logger.error("Cannot connect to Ethereum node at %s — falling back to mock.", rpc_url)
                self._mock_mode = True
                self._w3 = None
                return

            self._account = self._w3.eth.account.from_key(private_key)
            checksum_addr = Web3.to_checksum_address(contract_address)
            self._contract = self._w3.eth.contract(
                address=checksum_addr,
                abi=_CONTRACT_ABI,
            )
            logger.info(
                "BlockchainService: connected to Sepolia. "
                "Contract: %s  Wallet: %s",
                checksum_addr,
                self._account.address,
            )

    # ── Public API ───────────────────────────────────────────────────────────

    def record_handoff(
        self,
        shipment_id: str,
        status: str,
        risk_score: float,
    ) -> Optional[str]:
        """
        Record a handoff on-chain. Returns tx hash (or mock hash).
        Designed to be called from a FastAPI BackgroundTask — never awaited
        inside a route handler.
        """
        data_hash = _make_data_hash(shipment_id, status, risk_score)
        risk_int = min(100, max(0, int(risk_score)))

        if self._mock_mode:
            tx_hash = _mock_tx_hash(shipment_id, data_hash)
            logger.info("[MOCK] Handoff recorded: %s → %s", shipment_id, tx_hash)
            return tx_hash

        try:
            nonce = self._w3.eth.get_transaction_count(self._account.address)
            
            # Build transaction with EIP-1559 gas (type 0x2)
            tx = self._contract.functions.recordHandoff(
                shipment_id, data_hash, status, risk_int
            ).build_transaction({
                "from":                 self._account.address,
                "nonce":                nonce,
                "gas":                  800_000,
                "maxFeePerGas":         self._w3.eth.gas_price * 2,  # 2x current base fee
                "maxPriorityFeePerGas": self._w3.to_wei("2", "gwei"),  # Miner tip
                "type":                 "0x2",  # EIP-1559 transaction
            })
            
            # Sign and send
            signed = self._account.sign_transaction(tx)
            tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            
            # Wait for confirmation (up to 120 seconds)
            # BackgroundTask context makes blocking acceptable
            try:
                receipt = self._w3.eth.wait_for_transaction_receipt(
                    tx_hash_bytes, timeout=120
                )
                
                # Check if transaction actually succeeded on-chain
                if receipt.status == 0:
                    logger.error(
                        "[SEPOLIA] TX REVERTED for shipment %s. "
                        "Check: 1) wallet matches contract owner 2) sufficient gas 3) contract state",
                        shipment_id
                    )
                    return _mock_tx_hash(shipment_id, data_hash)  # fallback
                    
            except Exception as timeout_exc:
                logger.warning(
                    "[SEPOLIA] TX not confirmed in 120s for shipment %s: %s",
                    shipment_id, timeout_exc
                )
                return _mock_tx_hash(shipment_id, data_hash)  # fallback
            
            # Success
            tx_hash = tx_hash_bytes.hex()
            logger.info("[SEPOLIA] TX recorded: %s", tx_hash)
            return tx_hash
            
        except ValueError as ve:
            # Likely contract/address mismatch or encoding error
            logger.error(
                "[BLOCKCHAIN] ValueError (likely contract/encoding): %s | Shipment: %s",
                ve, shipment_id
            )
            return _mock_tx_hash(shipment_id, data_hash)
        except Exception as exc:
            logger.error(
                "[BLOCKCHAIN WRITE FAILED] Unexpected error: %s | Shipment: %s | "
                "Next steps: Check wallet owns contract, check ETH balance, verify contract ABI",
                exc, shipment_id
            )
            return _mock_tx_hash(shipment_id, data_hash)

    def flag_shipment(self, shipment_id: str, reason: str) -> Optional[str]:
        """Flag an existing shipment on-chain."""
        if self._mock_mode:
            h = hashlib.sha256(f"flag:{shipment_id}:{reason}".encode()).hexdigest()
            tx_hash = f"mock:flag:{h}"
            logger.info("[MOCK] Shipment flagged: %s → %s", shipment_id, tx_hash)
            return tx_hash

        try:
            nonce = self._w3.eth.get_transaction_count(self._account.address)
            tx = self._contract.functions.flagShipment(
                shipment_id, reason
            ).build_transaction({
                "from":     self._account.address,
                "nonce":    nonce,
                "gas":      500_000,
                "gasPrice": self._w3.eth.gas_price,
            })
            signed = self._account.sign_transaction(tx)
            tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            return tx_hash_bytes.hex()
        except Exception as exc:
            logger.error("Flag tx failed for %s: %s", shipment_id, exc)
            h = hashlib.sha256(f"flag:{shipment_id}:{reason}".encode()).hexdigest()
            return f"mock:flag:{h}"

    def get_handoff(self, shipment_id: str) -> Optional[dict]:
        """
        Read handoff record from chain.
        Returns None in mock mode (no on-chain state to read).
        """
        if self._mock_mode:
            return None

        try:
            result = self._contract.functions.getHandoff(shipment_id).call()
            return {
                "data_hash":   result[0],
                "status":      result[1],
                "risk_score":  result[2],
                "timestamp":   result[3],
                "flag_reason": result[4],
            }
        except Exception as exc:
            logger.error("get_handoff failed for %s: %s", shipment_id, exc)
            return None

    @property
    def is_mock(self) -> bool:
        return self._mock_mode


# ── Singleton instance (initialised in main.py startup) ─────────────────────
_service: Optional[BlockchainService] = None


def init_blockchain_service(rpc_url: str, private_key: str, contract_address: str) -> BlockchainService:
    global _service
    _service = BlockchainService(rpc_url, private_key, contract_address)
    return _service


def get_blockchain_service() -> BlockchainService:
    if _service is None:
        raise RuntimeError("BlockchainService not initialised — call init_blockchain_service() at startup")
    return _service


# ── BackgroundTask helpers (called from route handlers) ──────────────────────
def bg_record_handoff_and_store(
    shipment_id: str,
    status: str,
    risk_score: float,
    db_session_factory,        # callable → Session
    model_class,               # Shipment or MedicineBatch
    record_id: str,
    hash_column: str = "blockchain_hash",
) -> None:
    """
    Background task:
      1. Record handoff on-chain
      2. Write tx hash back to the DB record
    Called via: BackgroundTasks.add_task(bg_record_handoff_and_store, ...)
    """
    svc = get_blockchain_service()
    tx_hash = svc.record_handoff(shipment_id, status, risk_score)

    if tx_hash:
        db = db_session_factory()
        try:
            obj = db.query(model_class).filter(model_class.id == record_id).first()
            if obj:
                setattr(obj, hash_column, tx_hash)
                db.commit()
        except Exception as exc:
            logger.error("Failed to write blockchain_hash to DB: %s", exc)
            db.rollback()
        finally:
            db.close()
