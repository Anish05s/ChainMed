from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from config import settings
from models import (
    ApprovalLog,
    Shipment,
    MedicineBatch,
    HandoffRecord,
    Manufacturer,
    Supplier,
    Consumer,
    User,
    AdminOverrideRequest,
)
from shared.schemas import ApprovalLogItem, PublicShipmentResponse, HandoffPublicItem, MedicineCatalogItem, DisputeSubmitRequest
from models import MedicineCatalog
from auth.dependencies import get_current_user
from audit_chain import write_approval_log
import math

router = APIRouter(prefix="/shared", tags=["Shared"])

@router.get("/catalog/medicines", response_model=List[MedicineCatalogItem])
def get_medicine_catalog(query: Optional[str] = None, db: Session = Depends(get_db)):
    if query:
        return db.query(MedicineCatalog).filter(MedicineCatalog.medicine_name.ilike(f"%{query}%")).limit(50).all()
    return db.query(MedicineCatalog).limit(50).all()


def _entity_name(db: Session, entity_id: Optional[str]) -> str:
    if not entity_id:
        return "Unknown"
    for model in (Manufacturer, Supplier, Consumer):
        row = db.query(model).filter(model.id == entity_id).first()
        if row:
            return row.name
    return entity_id


def _full_qr_url(qr_path: Optional[str]) -> Optional[str]:
    if not qr_path:
        return None
    if qr_path.startswith("http"):
        return qr_path
    return f"{settings.API_BASE_URL}{qr_path}"


@router.get("/shipment/{shipment_id}", response_model=PublicShipmentResponse)
def get_public_shipment(shipment_id: str, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    batch = db.query(MedicineBatch).filter(MedicineBatch.id == shipment.batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found for this shipment",
        )

    handoffs = (
        db.query(HandoffRecord)
        .filter(HandoffRecord.shipment_id == shipment.id)
        .order_by(HandoffRecord.submitted_at.asc())
        .all()
    )

    logs = (
        db.query(ApprovalLog)
        .filter(
            ApprovalLog.entity_id == shipment.id,
            ApprovalLog.entity_type == "shipment",
        )
        .order_by(ApprovalLog.created_at.asc())
        .all()
    )

    shipment_qty = (
        shipment.quantity_dispatched
        if shipment.quantity_dispatched is not None
        else batch.quantity
    )

    override_details = None
    from models import AdminOverrideRequest, AdminOverrideVote
    from shared.schemas import OverrideSummary
    
    if shipment.override_blockchain_hash:
        override_req = db.query(AdminOverrideRequest).filter(
            AdminOverrideRequest.shipment_id == shipment.id,
            AdminOverrideRequest.status == "executed"
        ).order_by(AdminOverrideRequest.executed_at.desc()).first()
        
        if override_req:
            votes = db.query(AdminOverrideVote).filter(
                AdminOverrideVote.override_request_id == override_req.id,
                AdminOverrideVote.vote == "approve"
            ).all()
            
            override_details = OverrideSummary(
                justification=override_req.justification,
                ai_cross_check=override_req.ai_cross_check,
                approvers=[v.admin_name for v in votes]
            )

    return PublicShipmentResponse(
        id=shipment.id,
        shipment_code=shipment.shipment_code,
        status=shipment.status,
        created_at=shipment.created_at,
        batch_name=batch.name,
        batch_number=batch.batch_number,
        medicine_quantity=shipment_qty,
        expiry_date=batch.expiry_date,
        from_entity_name=_entity_name(db, shipment.from_entity_id),
        to_entity_name=_entity_name(db, shipment.to_entity_id),
        qr_code_url=_full_qr_url(shipment.qr_code_url),
        blockchain_hash=shipment.blockchain_hash,
        override_blockchain_hash=shipment.override_blockchain_hash,
        override_details=override_details,
        handoffs=[HandoffPublicItem.model_validate(h) for h in handoffs],
        approval_logs=[ApprovalLogItem.model_validate(log) for log in logs],
    )


@router.post("/shipment/{shipment_id}/dispute", response_model=dict)
def submit_shipment_dispute(
    shipment_id: str,
    data: DisputeSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if shipment.status != "FLAGGED":
        raise HTTPException(status_code=400, detail="Shipment is not currently flagged")

    if current_user.entity_id not in [shipment.from_entity_id, shipment.to_entity_id]:
        raise HTTPException(status_code=403, detail="You are not authorized to dispute this shipment")

    # Check for existing pending request
    existing = db.query(AdminOverrideRequest).filter(
        AdminOverrideRequest.shipment_id == shipment_id,
        AdminOverrideRequest.status == "pending"
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="A dispute/override request is already pending for this shipment.")

    # Calculate 80% threshold of eligible admins
    eligible_admins_count = db.query(User).filter(
        User.role == "admin",
        User.sub_role != "admin_dev"
    ).count()
    
    if eligible_admins_count == 0:
        raise HTTPException(status_code=500, detail="No eligible admins found to approve this dispute.")
        
    required_approvals = max(1, math.ceil(eligible_admins_count * 0.8))

    req = AdminOverrideRequest(
        shipment_id=shipment_id,
        initiated_by=current_user.id,
        justification=data.justification,
        required_approvals=required_approvals,
        current_approvals=0,
        status="pending"
    )
    db.add(req)

    # Log the dispute submission
    write_approval_log(
        db,
        current_user,
        action_type="dispute_submitted",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=f"Dispute submitted: {data.justification}"
    )

    db.commit()
    return {"detail": "Dispute submitted successfully", "request_id": req.id}

