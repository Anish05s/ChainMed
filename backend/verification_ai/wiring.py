"""
verification_ai/wiring.py
─────────────────────────
Central helper called by supplier and consumer routers after a handoff
record is saved.  Loads all available handoff records for a shipment,
builds PartyReport objects, runs the cross-match engine, writes an
AIFlag row to the DB, and dispatches the blockchain BackgroundTask.

Rules (from master prompt):
  • < 2 handoffs   → return PENDING, no AIFlag written yet
  • 2 or 3 parties → run cross-match
  • FLAGGED        → call blockchain_service.flag_shipment()
  • VERIFIED       → add bg_record_handoff_and_store as BackgroundTask
  • Always write AIFlag to DB when we have >= 2 parties
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from models import AIFlag, HandoffRecord, MedicineBatch, Shipment
from verification_ai.engine import PartyReport, run_verification

logger = logging.getLogger(__name__)

# Stage name → which PartyReport field it fills
_STAGE_ROLE = {
    "manufacturer_dispatch": "manufacturer",
    "supplier_receipt":      "supplier",
    "hospital_receipt":      "hospital",
}


def _load_party_reports(
    db: Session, shipment_id: str, batch: MedicineBatch
) -> tuple[Optional[PartyReport], Optional[PartyReport], Optional[PartyReport]]:
    """
    Load all HandoffRecords for a shipment and build PartyReport objects.
    Returns (manufacturer_report, supplier_report, hospital_report).
    Any party that hasn't submitted yet will be None.
    """
    handoffs = (
        db.query(HandoffRecord)
        .filter(HandoffRecord.shipment_id == shipment_id)
        .all()
    )

    reports: dict[str, PartyReport] = {}
    for h in handoffs:
        role = _STAGE_ROLE.get(h.stage)
        if role is None:
            continue
        signature_valid = True
        if h.signature and h.public_key_pem:
            from auth.signing import verify_handoff_signature
            payload = {
                "shipment_id": shipment_id,
                "quantity_reported": h.quantity_reported,
                "quantity_commitment": h.quantity_commitment,
                "expiry_reported": h.expiry_reported.isoformat() if isinstance(h.expiry_reported, datetime) else None,
                "temp_reported": h.temp_reported,
            }
            signature_valid = verify_handoff_signature(h.public_key_pem, payload, h.signature)
        elif h.signature is None and h.public_key_pem is None:
            # For backward compatibility with old records, or missing keys
            signature_valid = False

        reports[role] = PartyReport(
            party=role,
            quantity=h.quantity_reported,
            expiry=h.expiry_reported if isinstance(h.expiry_reported, datetime) else None,
            temp=h.temp_reported,
            signature_valid=signature_valid,
        )

    # If supplier handoff is missing (because it's attached to the previous shipment)
    if "supplier" not in reports:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if shipment:
            sup_incoming = (
                db.query(Shipment)
                .filter(
                    Shipment.batch_id == shipment.batch_id,
                    Shipment.to_entity_id == shipment.from_entity_id
                )
                .first()
            )
            if sup_incoming:
                sup_handoff = (
                    db.query(HandoffRecord)
                    .filter(
                        HandoffRecord.shipment_id == sup_incoming.id,
                        HandoffRecord.stage == "supplier_receipt"
                    )
                    .first()
                )
                if sup_handoff:
                    signature_valid = True
                    if sup_handoff.signature and sup_handoff.public_key_pem:
                        from auth.signing import verify_handoff_signature
                        payload = {
                            "shipment_id": sup_incoming.id,
                            "quantity_reported": sup_handoff.quantity_reported,
                            "quantity_commitment": sup_handoff.quantity_commitment,
                            "expiry_reported": sup_handoff.expiry_reported.isoformat() if isinstance(sup_handoff.expiry_reported, datetime) else None,
                            "temp_reported": sup_handoff.temp_reported,
                        }
                        signature_valid = verify_handoff_signature(sup_handoff.public_key_pem, payload, sup_handoff.signature)
                    elif sup_handoff.signature is None and sup_handoff.public_key_pem is None:
                        signature_valid = False

                    reports["supplier"] = PartyReport(
                        party="supplier",
                        quantity=sup_handoff.quantity_reported,
                        expiry=sup_handoff.expiry_reported if isinstance(sup_handoff.expiry_reported, datetime) else None,
                        temp=sup_handoff.temp_reported,
                        signature_valid=signature_valid,
                    )

    # Manufacturer report: if no explicit manufacturer handoff, use batch data
    if "manufacturer" not in reports:
        mfg_qty = batch.quantity
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if shipment:
            if shipment.from_entity_id == batch.manufacturer_id:
                mfg_qty = shipment.quantity_dispatched
            else:
                sup_incoming = (
                    db.query(Shipment)
                    .filter(
                        Shipment.batch_id == shipment.batch_id,
                        Shipment.to_entity_id == shipment.from_entity_id
                    )
                    .first()
                )
                if sup_incoming:
                    mfg_qty = sup_incoming.quantity_dispatched

        reports["manufacturer"] = PartyReport(
            party="manufacturer",
            quantity=mfg_qty,
            expiry=batch.expiry_date if isinstance(batch.expiry_date, datetime) else None,
            temp=batch.storage_temp_declared,
        )

    return (
        reports.get("manufacturer"),
        reports.get("supplier"),
        reports.get("hospital"),
    )


def trigger_verification_and_blockchain(
    shipment_id: str,
    db: Session,
    background_tasks: BackgroundTasks,
    hospital_shipment_id: Optional[str] = None,
    approval_log_id: Optional[str] = None,
) -> dict:
    """
    Called from supplier/router.py and consumer/router.py after a handoff
    record is saved.

    Returns a dict with keys: status, risk_score, explanation, ai_flag_id
    """
    from blockchain_service.service import bg_record_handoff_and_store, get_blockchain_service
    from database import SessionLocal

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        logger.warning("trigger_verification: shipment %s not found", shipment_id)
        return {"status": "PENDING", "risk_score": 0, "explanation": "Shipment not found", "ai_flag_id": None}

    batch = db.query(MedicineBatch).filter(MedicineBatch.id == shipment.batch_id).first()
    if not batch:
        logger.warning("trigger_verification: batch not found for shipment %s", shipment_id)
        return {"status": "PENDING", "risk_score": 0, "explanation": "Batch not found", "ai_flag_id": None}

    mfr, sup, hos = _load_party_reports(db, shipment_id, batch)

    # Need at least supplier to cross-match (manufacturer data always available from batch)
    if sup is None:
        return {
            "status": "PENDING",
            "risk_score": 0,
            "explanation": "Waiting for: supplier",
            "ai_flag_id": None,
        }

    # Find supplier_dispatched from outbound shipment if available
    supplier_dispatched: Optional[int] = None
    
    if hospital_shipment_id is not None and hospital_shipment_id == shipment_id:
        # The current shipment IS the outbound shipment (supplier -> hospital)
        supplier_dispatched = shipment.quantity_dispatched
    else:
        # The current shipment is manufacturer -> supplier
        # Look for an outbound shipment from supplier to hospital for this batch
        outbound = (
            db.query(Shipment)
            .filter(
                Shipment.batch_id == shipment.batch_id,
                Shipment.from_entity_id == shipment.to_entity_id,  # supplier is the from
            )
            .first()
        )
        if outbound and outbound.quantity_dispatched:
            supplier_dispatched = outbound.quantity_dispatched

    result = run_verification(
        manufacturer=mfr,
        supplier=sup,
        hospital=hos,
        hospital_shipment_id=hospital_shipment_id or shipment_id,
        supplier_dispatched=supplier_dispatched,
    )

    # Write AIFlag record
    ai_flag = AIFlag(
        shipment_id=shipment_id,
        risk_score=result.risk_score,
        status=result.status,
        triggered_rules=result.triggered_rules_json(),
        mismatch_details=result.mismatch_details_json(),
        explanation=result.explanation,
    )
    db.add(ai_flag)
    db.flush()

    if result.status == "FLAGGED":
        ai_flag_id = ai_flag.id  # capture before session closes
        background_tasks.add_task(
            _update_explanation_with_llm,
            ai_flag_id=ai_flag_id,
            manufacturer=mfr,
            supplier=sup,
            hospital=hos,
            result=result,
            db_session_factory=SessionLocal,
        )

    logger.info(
        "AIFlag written for shipment %s: status=%s risk=%.0f",
        shipment_id, result.status, result.risk_score,
    )

    # Always record handoff on-chain first.
    # If FLAGGED, flag_shipment must come AFTER record_handoff completes on-chain
    # to avoid the "Handoff not found" revert. We use a single sequential task.
    if result.status == "FLAGGED":
        background_tasks.add_task(
            _record_then_flag,
            shipment_id=shipment_id,
            status=result.status,
            risk_score=result.risk_score,
            flag_reason=result.explanation[:200],
            db_session_factory=SessionLocal,
            approval_log_id=approval_log_id,
        )
        logger.info("Queued sequential record+flag blockchain tasks for shipment %s", shipment_id)
    else:
        background_tasks.add_task(
            bg_record_handoff_and_store,
            shipment_id,
            result.status,
            result.risk_score,
            SessionLocal,
            Shipment,
            shipment_id,
            "blockchain_hash",
            approval_log_id,
        )
        logger.info("Queued blockchain handoff record for shipment %s", shipment_id)

    return {
        "status": result.status,
        "risk_score": result.risk_score,
        "explanation": result.explanation,
        "ai_flag_id": ai_flag.id,
    }

def _update_explanation_with_llm(
    ai_flag_id: str,
    manufacturer,
    supplier,
    hospital,
    result,
    db_session_factory,
):
    """
    BackgroundTask: calls Gemini and patches the explanation in DB.
    Runs asynchronously, never blocks the route.
    """
    try:
        from verification_ai.llm_investigator import investigate_flag
        
        llm_text = investigate_flag(
            batch_name=getattr(manufacturer, "batch_name", "Unknown"),
            batch_number=getattr(manufacturer, "batch_number", "Unknown"),
            from_entity=manufacturer.party if manufacturer else "Unknown",
            to_entity=hospital.party if hospital else "Unknown",
            risk_score=result.risk_score,
            triggered_rules=result.triggered_rules,
            mismatch_details=result.mismatches,
            rule_explanation=result.explanation,
        )
        
        if not llm_text:
            return
        
        db = db_session_factory()
        try:
            flag = db.query(AIFlag).filter(AIFlag.id == ai_flag_id).first()
            if flag:
                flag.explanation = llm_text
                db.commit()
        finally:
            db.close()
            
    except Exception as exc:
        logger.error("[wiring] LLM background update failed: %s", exc)


def _record_then_flag(
    shipment_id: str,
    status: str,
    risk_score: float,
    flag_reason: str,
    db_session_factory,
    approval_log_id: str = None,
) -> None:
    """
    Sequential BackgroundTask for FLAGGED shipments.
    
    Order matters on-chain:
      1. recordHandoff() — creates the record, waits for confirmation
      2. flagShipment()  — updates the record's status/reason
    
    Running them as separate background tasks caused a race condition where
    flagShipment() executed before recordHandoff() was mined, causing the
    'Handoff not found' revert on Sepolia.
    """
    from blockchain_service.service import get_blockchain_service, _make_data_hash, _mock_tx_hash

    svc = get_blockchain_service()

    # Step 1: Record handoff (blocks until mined or times out in real mode)
    tx_hash = svc.record_handoff(shipment_id, status, risk_score)
    logger.info("[blockchain] recordHandoff tx for %s: %s", shipment_id, tx_hash)

    # Step 2:
    if tx_hash:
        from models import Shipment, ApprovalLog
        db = db_session_factory()
        try:
            sh = db.query(Shipment).filter(Shipment.id == shipment_id).first()
            if sh:
                sh.blockchain_hash = tx_hash
                sh.status = status
            
            if approval_log_id:
                log_obj = db.query(ApprovalLog).filter(ApprovalLog.id == approval_log_id).first()
                if log_obj:
                    log_obj.blockchain_hash = tx_hash
                    
            db.commit()
        except Exception as exc:
            logger.error("[blockchain] Failed to write blockchain_hash: %s", exc)
            db.rollback()
        finally:
            db.close()

    # Step 3: Now that the handoff is confirmed on-chain, flag it
    # (In mock mode this is a no-op effectively, but still safe to call)
    flag_tx = svc.flag_shipment(shipment_id, flag_reason)
    logger.info("[blockchain] flagShipment tx for %s: %s", shipment_id, flag_tx)
