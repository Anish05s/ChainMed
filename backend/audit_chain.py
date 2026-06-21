"""
audit_chain.py — Shared approval log writer with hash chain
===========================================================
Centralises _write_approval_log so the hash-chain logic exists in ONE place
instead of being duplicated across manufacturer/supplier/consumer routers.

The hash chain:
  log_hash = SHA-256(
      id + actor_role + actor_name + actor_id + action_type +
      entity_id + entity_type + notes + signature + previous_hash
  )

This makes it cryptographically detectable if any past row is altered:
re-walking the chain and recomputing hashes will produce a mismatch at
the tampered row and every subsequent row.
"""

import hashlib
import json
import logging

from sqlalchemy.orm import Session

from models import ApprovalLog, User
from auth.signing import sign_handoff

logger = logging.getLogger(__name__)


def _compute_log_hash(log: ApprovalLog, previous_hash: str | None) -> str:
    """
    Compute the deterministic SHA-256 hash for an ApprovalLog row.
    All fields that represent the meaning of the log entry are included.
    None values are normalised to empty strings for consistency.
    """
    payload = json.dumps(
        {
            "id":          log.id or "",
            "actor_role":  log.actor_role or "",
            "actor_name":  log.actor_name or "",
            "actor_id":    log.actor_id or "",
            "action_type": log.action_type or "",
            "entity_id":   log.entity_id or "",
            "entity_type": log.entity_type or "",
            "notes":       log.notes or "",
            "signature":   log.signature or "",
            "previous_hash": previous_hash or "GENESIS",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def write_approval_log(
    db: Session,
    user: User,
    action_type: str,
    entity_id: str,
    entity_type: str,
    notes: str,
    signed_payload: dict = None,
) -> ApprovalLog:
    """
    Create and add an ApprovalLog to the session, with hash chain links.

    Replaces the duplicated _write_approval_log functions in each router.
    Call db.flush() or db.commit() after to persist.
    """
    # 1. Sign the payload if a signed_payload is provided
    signature = None
    if signed_payload and user.private_key_pem:
        try:
            signature = sign_handoff(user.private_key_pem, signed_payload)
        except Exception as exc:
            logger.warning("Could not sign approval log payload: %s", exc)

    # 2. Fetch the most recent log's hash to chain from
    last_log = (
        db.query(ApprovalLog)
        .order_by(ApprovalLog.created_at.desc())
        .first()
    )
    previous_hash = last_log.log_hash if (last_log and last_log.log_hash) else None

    # 3. Build the log entry (id not yet assigned by SQLAlchemy, use gen_uuid manually)
    from models import gen_uuid
    log_id = gen_uuid()

    log = ApprovalLog(
        id=log_id,
        actor_role=user.sub_role,
        actor_name=user.full_name or user.email,
        actor_id=user.id,
        action_type=action_type,
        entity_id=entity_id,
        entity_type=entity_type,
        notes=notes,
        signature=signature,
        signer_address=user.public_key_pem,
        previous_hash=previous_hash,
    )

    # 4. Compute and attach the hash (must happen before db.add so id is stable)
    log.log_hash = _compute_log_hash(log, previous_hash)

    db.add(log)
    return log
