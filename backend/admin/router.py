from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import math

from database import get_db
from models import (
    User, Shipment, AIFlag, ApprovalLog, MedicineBatch, 
    AdminOverrideRequest, AdminOverrideVote
)
from auth.dependencies import require_admin
from auth.signing import sign_handoff
from verification_ai.llm_investigator import cross_check_override
from blockchain_service.service import get_blockchain_service
from admin.schemas import (
    FlaggedShipmentResponse, OverrideRequest, OverrideVoteRequest,
    OverrideRequestResponse, AdminOverrideVoteResponse
)

router = APIRouter(prefix="/admin", tags=["Admin"])


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
        # Check if there is an active override request
        active_req = db.query(AdminOverrideRequest).filter(
            AdminOverrideRequest.shipment_id == shipment.id,
            AdminOverrideRequest.status == "pending"
        ).first()
        
        results.append(FlaggedShipmentResponse(
            shipment_id=shipment.id,
            shipment_code=shipment.shipment_code,
            medicine_name=batch.name,
            batch_number=batch.batch_number,
            from_entity_id=shipment.from_entity_id,
            to_entity_id=shipment.to_entity_id,
            risk_score=flag.risk_score,
            explanation=flag.explanation,
            status=flag.status,
            active_override_request_id=active_req.id if active_req else None
        ))
    return results


@router.post("/flags/{shipment_id}/override", response_model=OverrideRequestResponse)
def initiate_override_request(
    shipment_id: str,
    data: OverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if current_user.sub_role == "admin_dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technical Overseer (admin_dev) cannot initiate overrides."
        )

    flag = db.query(AIFlag).filter(AIFlag.shipment_id == shipment_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="AI Flag not found")
    
    if flag.status == "OVERRIDDEN":
        raise HTTPException(status_code=400, detail="Flag already overridden")

    # Check for existing pending request
    existing = db.query(AdminOverrideRequest).filter(
        AdminOverrideRequest.shipment_id == shipment_id,
        AdminOverrideRequest.status == "pending"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An override request is already pending for this shipment.")

    # Calculate 80% threshold of eligible admins
    eligible_admins_count = db.query(User).filter(
        User.role == "admin",
        User.sub_role != "admin_dev"
    ).count()
    
    if eligible_admins_count == 0:
        raise HTTPException(status_code=500, detail="No eligible admins found to approve.")
        
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
    db.commit()
    db.refresh(req)
    
    return req


@router.get("/overrides", response_model=List[OverrideRequestResponse])
def list_override_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    reqs = db.query(AdminOverrideRequest).order_by(AdminOverrideRequest.created_at.desc()).all()
    # Eager loading or simple return since we don't return votes list here (Optional=None by default)
    return reqs


@router.get("/overrides/{override_id}", response_model=OverrideRequestResponse)
def get_override_detail(
    override_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    req = db.query(AdminOverrideRequest).filter(AdminOverrideRequest.id == override_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Override request not found")
        
    votes = db.query(AdminOverrideVote).filter(AdminOverrideVote.override_request_id == override_id).all()
    
    resp = OverrideRequestResponse(
        id=req.id,
        shipment_id=req.shipment_id,
        initiated_by=req.initiated_by,
        justification=req.justification,
        status=req.status,
        required_approvals=req.required_approvals,
        current_approvals=req.current_approvals,
        override_blockchain_hash=req.override_blockchain_hash,
        ai_cross_check=req.ai_cross_check,
        created_at=req.created_at,
        executed_at=req.executed_at,
        votes=[AdminOverrideVoteResponse(
            id=v.id, admin_id=v.admin_id, admin_name=v.admin_name, 
            admin_sub_role=v.admin_sub_role, vote=v.vote, created_at=v.created_at
        ) for v in votes]
    )
    return resp


@router.post("/overrides/{override_id}/vote")
def vote_on_override(
    override_id: str,
    data: OverrideVoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if current_user.sub_role == "admin_dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technical Overseer (admin_dev) cannot vote on overrides."
        )

    req = db.query(AdminOverrideRequest).filter(AdminOverrideRequest.id == override_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Override request not found")
        
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    # Check if already voted
    existing_vote = db.query(AdminOverrideVote).filter(
        AdminOverrideVote.override_request_id == override_id,
        AdminOverrideVote.admin_id == current_user.id
    ).first()
    if existing_vote:
        raise HTTPException(status_code=400, detail="You have already voted on this request.")

    # Cast vote
    signed_payload = {
        "action": "admin_override_vote",
        "override_request_id": override_id,
        "vote": data.vote,
        "admin_id": current_user.id,
    }
    signature = sign_handoff(current_user.private_key_pem, signed_payload) if current_user.private_key_pem else None

    vote = AdminOverrideVote(
        override_request_id=override_id,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email,
        admin_sub_role=current_user.sub_role,
        vote=data.vote,
        signature=signature
    )
    db.add(vote)
    
    if data.vote == "approve":
        req.current_approvals += 1

    db.commit()
    db.refresh(req)

    # Check threshold
    if req.current_approvals >= req.required_approvals:
        # Threshold met! Execute the override
        req.status = "executed"
        from models import now
        req.executed_at = now()
        
        # Update flag and shipment
        flag = db.query(AIFlag).filter(AIFlag.shipment_id == req.shipment_id).first()
        shipment = db.query(Shipment).filter(Shipment.id == req.shipment_id).first()
        if flag: flag.status = "OVERRIDDEN"
        if shipment: shipment.status = "delivered"
        
        # Enqueue background task to do cross-check and blockchain writing
        background_tasks.add_task(
            execute_override_async,
            override_id=req.id,
        )
        
        db.commit()
        return {"status": "executed", "message": "Approval threshold met. Override executing."}

    return {"status": "voted", "message": "Vote recorded."}


def execute_override_async(override_id: str):
    """Background task to run AI cross-check and blockchain recording."""
    db = next(get_db())
    try:
        req = db.query(AdminOverrideRequest).filter(AdminOverrideRequest.id == override_id).first()
        if not req: return
        
        flag = db.query(AIFlag).filter(AIFlag.shipment_id == req.shipment_id).first()
        if not flag: return

        # 1. AI Cross-check
        ai_assessment = cross_check_override(
            risk_score=flag.risk_score,
            triggered_rules=flag.triggered_rules or "",
            mismatch_details=flag.mismatch_details or "",
            admin_justification=req.justification
        )
        req.ai_cross_check = ai_assessment

        # 2. Blockchain Recording
        votes = db.query(AdminOverrideVote).filter(
            AdminOverrideVote.override_request_id == override_id,
            AdminOverrideVote.vote == "approve"
        ).all()
        approvers = [v.admin_name for v in votes]

        svc = get_blockchain_service()
        tx_hash = svc.record_override(
            shipment_id=req.shipment_id,
            justification=req.justification,
            approving_admins=approvers,
            ai_cross_check=ai_assessment
        )
        
        req.override_blockchain_hash = tx_hash
        
        shipment = db.query(Shipment).filter(Shipment.id == req.shipment_id).first()
        if shipment:
            shipment.override_blockchain_hash = tx_hash

        # 3. Create Approval Log
        log = ApprovalLog(
            actor_role="multi_sig_admins",
            actor_name=", ".join(approvers),
            action_type="admin_override",
            entity_id=req.shipment_id,
            entity_type="shipment",
            notes=f"Multi-Sig Override Executed. Justification: {req.justification} | AI Check: {ai_assessment}",
            blockchain_hash=tx_hash
        )
        db.add(log)
        db.commit()

    except Exception as e:
        import logging
        logging.error(f"Failed to execute override async: {e}")
        db.rollback()
    finally:
        db.close()

