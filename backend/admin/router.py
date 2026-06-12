from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from database import get_db
from models import User, Shipment, AIFlag, ApprovalLog, MedicineBatch, VerificationStatus
from auth.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

class FlaggedShipmentResponse(BaseModel):
    shipment_id: str
    shipment_code: str
    medicine_name: str
    batch_number: str
    from_entity_id: str
    to_entity_id: str
    risk_score: float
    explanation: str
    status: str

class OverrideRequest(BaseModel):
    justification: str

@router.get("/flags", response_model=List[FlaggedShipmentResponse])
def get_flagged_shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # All admins can view flags
    flags = (
        db.query(AIFlag, Shipment, MedicineBatch)
        .join(Shipment, AIFlag.shipment_id == Shipment.id)
        .join(MedicineBatch, Shipment.batch_id == MedicineBatch.id)
        .filter(AIFlag.status == "FLAGGED")
        .all()
    )
    
    results = []
    for flag, shipment, batch in flags:
        results.append(FlaggedShipmentResponse(
            shipment_id=shipment.id,
            shipment_code=shipment.shipment_code,
            medicine_name=batch.name,
            batch_number=batch.batch_number,
            from_entity_id=shipment.from_entity_id,
            to_entity_id=shipment.to_entity_id,
            risk_score=flag.risk_score,
            explanation=flag.explanation,
            status=flag.status
        ))
    return results


@router.post("/flags/{shipment_id}/override", status_code=status.HTTP_200_OK)
def override_flag(
    shipment_id: str,
    data: OverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Only master and manager can override
    if current_user.sub_role == "admin_dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technical Overseer (admin_dev) cannot override compliance flags."
        )

    flag = db.query(AIFlag).filter(AIFlag.shipment_id == shipment_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="AI Flag not found")
    
    if flag.status == "OVERRIDDEN":
        raise HTTPException(status_code=400, detail="Flag already overridden")

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    flag.status = "OVERRIDDEN"
    shipment.status = "delivered" # or whatever the final state is

    from auth.signing import sign_handoff

    signed_payload = {
        "action": "admin_override",
        "shipment_id": shipment.id,
        "justification": data.justification,
        "admin_id": current_user.id,
    }

    signature = None
    if current_user.private_key_pem:
        signature = sign_handoff(current_user.private_key_pem, signed_payload)

    log = ApprovalLog(
        actor_role=current_user.sub_role,
        actor_name=current_user.full_name or current_user.email,
        actor_id=current_user.id,
        action_type="admin_override",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=f"Admin Override: {data.justification}",
        signature=signature,
        signer_address=current_user.public_key_pem,
    )
    db.add(log)
    db.commit()

    return {"status": "success", "message": "Shipment flag overridden successfully."}
