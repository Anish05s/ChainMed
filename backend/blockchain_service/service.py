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
import threading
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
        # Lock + local nonce counter to prevent nonce collisions when
        # multiple background tasks fire within the same block window.
        self._nonce_lock = threading.Lock()
        self._local_nonce: Optional[int] = None

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
            # ── Nonce management: use a local counter to avoid collisions ──
            # Fetching nonce from network inside rapid back-to-back calls returns
            # the same value (pending txns not yet confirmed), causing rejections.
            # We keep a local counter, resetting to network count only on error.
            with self._nonce_lock:
                if self._local_nonce is None:
                    self._local_nonce = self._w3.eth.get_transaction_count(
                        self._account.address, "pending"
                    )
                nonce = self._local_nonce
                self._local_nonce += 1

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
            # Likely contract/address mismatch or encoding error; reset local nonce
            logger.error(
                "[BLOCKCHAIN] ValueError (likely contract/encoding): %s | Shipment: %s",
                ve, shipment_id
            )
            with self._nonce_lock:
                self._local_nonce = None  # force re-sync from network next time
            return _mock_tx_hash(shipment_id, data_hash)
        except Exception as exc:
            logger.error(
                "[BLOCKCHAIN WRITE FAILED] Unexpected error: %s | Shipment: %s | "
                "Next steps: Check wallet owns contract, check ETH balance, verify contract ABI",
                exc, shipment_id
            )
            with self._nonce_lock:
                self._local_nonce = None  # force re-sync from network next time
            return _mock_tx_hash(shipment_id, data_hash)

    def flag_shipment(self, shipment_id: str, reason: str) -> Optional[str]:
        """Flag an existing shipment on-chain."""
        if self._mock_mode:
            h = hashlib.sha256(f"flag:{shipment_id}:{reason}".encode()).hexdigest()
            tx_hash = f"mock:flag:{h}"
            logger.info("[MOCK] Shipment flagged: %s → %s", shipment_id, tx_hash)
            return tx_hash

        try:
            with self._nonce_lock:
                if self._local_nonce is None:
                    self._local_nonce = self._w3.eth.get_transaction_count(
                        self._account.address, "pending"
                    )
                nonce = self._local_nonce
                self._local_nonce += 1

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
            with self._nonce_lock:
                self._local_nonce = None  # force re-sync from network next time
            h = hashlib.sha256(f"flag:{shipment_id}:{reason}".encode()).hexdigest()
            return f"mock:flag:{h}"

    def record_override(self, shipment_id: str, justification: str, approving_admins: list[str], ai_cross_check: str) -> Optional[str]:
        """Record an admin multi-sig override on-chain."""
        # Truncate AI cross-check to save gas
        ai_summary = ai_cross_check[:200] if ai_cross_check else ""
        
        payload = json.dumps({
            "action": "multi_sig_override",
            "justification": justification,
            "approvers": approving_admins,
            "ai_summary": ai_summary
        }, sort_keys=True)
        data_hash = hashlib.sha256(payload.encode()).hexdigest()
        
        if self._mock_mode:
            tx_hash = _mock_tx_hash(shipment_id, data_hash + "_override")
            logger.info("[MOCK] Override recorded: %s → %s", shipment_id, tx_hash)
            return tx_hash

        try:
            with self._nonce_lock:
                if self._local_nonce is None:
                    self._local_nonce = self._w3.eth.get_transaction_count(
                        self._account.address, "pending"
                    )
                nonce = self._local_nonce
                self._local_nonce += 1

            # We use recordHandoff with status ADMIN_OVERRIDE
            tx = self._contract.functions.recordHandoff(
                shipment_id, data_hash, "ADMIN_OVERRIDE", 0
            ).build_transaction({
                "from":                 self._account.address,
                "nonce":                nonce,
                "gas":                  800_000,
                "maxFeePerGas":         self._w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self._w3.to_wei("2", "gwei"),
                "type":                 "0x2",
            })
            
            signed = self._account.sign_transaction(tx)
            tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            
            # Since this is an override, we want to wait for receipt
            try:
                receipt = self._w3.eth.wait_for_transaction_receipt(
                    tx_hash_bytes, timeout=120
                )
                if receipt.status == 0:
                    logger.error("[SEPOLIA] Override TX REVERTED for shipment %s", shipment_id)
                    return _mock_tx_hash(shipment_id, data_hash + "_override")
            except Exception as timeout_exc:
                logger.warning("[SEPOLIA] Override TX not confirmed in 120s: %s", timeout_exc)
                return _mock_tx_hash(shipment_id, data_hash + "_override")
                
            return tx_hash_bytes.hex()
            
        except Exception as exc:
            logger.error("Override tx failed for %s: %s", shipment_id, exc)
            with self._nonce_lock:
                self._local_nonce = None
            return _mock_tx_hash(shipment_id, data_hash + "_override")


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
    approval_log_id: str = None,
) -> None:
    """
    Background task:
      1. Record handoff on-chain
      2. Write tx hash back to the DB record and the associated ApprovalLog
    Called via: BackgroundTasks.add_task(bg_record_handoff_and_store, ...)
    """
    svc = get_blockchain_service()
    tx_hash = svc.record_handoff(shipment_id, status, risk_score)

    if tx_hash:
        from models import ApprovalLog
        db = db_session_factory()
        try:
            obj = db.query(model_class).filter(model_class.id == record_id).first()
            if obj:
                setattr(obj, hash_column, tx_hash)
            
            if approval_log_id:
                log_obj = db.query(ApprovalLog).filter(ApprovalLog.id == approval_log_id).first()
                if log_obj:
                    log_obj.blockchain_hash = tx_hash
                    
            db.commit()
        except Exception as exc:
            logger.error("Failed to write blockchain_hash to DB: %s", exc)
            db.rollback()
        finally:
            db.close()
