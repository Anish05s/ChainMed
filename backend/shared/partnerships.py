from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
from models import TradePartnership, User
from auth.dependencies import get_current_user

router = APIRouter(prefix="/shared/partnerships", tags=["Partnerships"])

class PartnershipRequest(BaseModel):
    partner_entity_id: str

class PartnershipResponse(BaseModel):
    id: str
    from_entity_id: str
    to_entity_id: str
    from_entity_type: str
    to_entity_type: str
    status: str
    requested_by: str | None

@router.get("", response_model=List[PartnershipResponse])
def get_partnerships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity_id = current_user.entity_id
    if not entity_id:
        raise HTTPException(status_code=400, detail="User has no entity associated")
        
    partnerships = db.query(TradePartnership).filter(
        (TradePartnership.from_entity_id == entity_id) | 
        (TradePartnership.to_entity_id == entity_id)
    ).order_by(TradePartnership.created_at.desc()).all()
    
    return partnerships

@router.post("/request", response_model=PartnershipResponse, status_code=status.HTTP_201_CREATED)
def request_partnership(
    data: PartnershipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity_id = current_user.entity_id
    if not entity_id:
        raise HTTPException(status_code=400, detail="User has no entity associated")
        
    partner_id = data.partner_entity_id
    if entity_id == partner_id:
        raise HTTPException(status_code=400, detail="Cannot partner with yourself")
        
    # Check if a partnership already exists (active or pending)
    existing = db.query(TradePartnership).filter(
        ((TradePartnership.from_entity_id == entity_id) & (TradePartnership.to_entity_id == partner_id)) |
        ((TradePartnership.from_entity_id == partner_id) & (TradePartnership.to_entity_id == entity_id))
    ).first()
    
    if existing:
        if existing.status in ["active", "pending"]:
            raise HTTPException(status_code=400, detail=f"Partnership is already {existing.status}")
        else:
            # Reactivate rejected/revoked
            existing.status = "pending"
            existing.requested_by = entity_id
            db.commit()
            db.refresh(existing)
            return existing

    # Figure out from/to and types
    # Rules: Manufacturer -> Supplier, Supplier -> Consumer
    my_type = current_user.role
    
    # We need the partner's type
    partner_user = db.query(User).filter(User.entity_id == partner_id).first()
    if not partner_user:
        raise HTTPException(status_code=404, detail="Partner entity not found")
        
    partner_type = partner_user.role
    
    from_entity_id = ""
    to_entity_id = ""
    from_entity_type = ""
    to_entity_type = ""
    
    if my_type == "manufacturer" and partner_type == "supplier":
        from_entity_id, to_entity_id = entity_id, partner_id
        from_entity_type, to_entity_type = "manufacturer", "supplier"
    elif my_type == "supplier" and partner_type == "manufacturer":
        from_entity_id, to_entity_id = partner_id, entity_id
        from_entity_type, to_entity_type = "manufacturer", "supplier"
    elif my_type == "supplier" and partner_type == "consumer":
        from_entity_id, to_entity_id = entity_id, partner_id
        from_entity_type, to_entity_type = "supplier", "consumer"
    elif my_type == "consumer" and partner_type == "supplier":
        from_entity_id, to_entity_id = partner_id, entity_id
        from_entity_type, to_entity_type = "supplier", "consumer"
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid partnership pairing: {my_type} and {partner_type}"
        )
        
    tp = TradePartnership(
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        from_entity_type=from_entity_type,
        to_entity_type=to_entity_type,
        requested_by=entity_id,
        status="pending"
    )
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return tp

@router.post("/{id}/accept", response_model=PartnershipResponse)
def accept_partnership(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity_id = current_user.entity_id
    tp = db.query(TradePartnership).filter(TradePartnership.id == id).first()
    if not tp:
        raise HTTPException(status_code=404, detail="Partnership not found")
        
    if tp.from_entity_id != entity_id and tp.to_entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Not a party to this partnership")
        
    if tp.requested_by == entity_id:
        raise HTTPException(status_code=400, detail="Cannot accept your own request")
        
    if tp.status != "pending":
        raise HTTPException(status_code=400, detail="Partnership is not pending")
        
    tp.status = "active"
    db.commit()
    db.refresh(tp)
    return tp

@router.post("/{id}/reject", response_model=PartnershipResponse)
def reject_partnership(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity_id = current_user.entity_id
    tp = db.query(TradePartnership).filter(TradePartnership.id == id).first()
    if not tp:
        raise HTTPException(status_code=404, detail="Partnership not found")
        
    if tp.from_entity_id != entity_id and tp.to_entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Not a party to this partnership")
        
    if tp.requested_by == entity_id:
        raise HTTPException(status_code=400, detail="Cannot reject your own request, use delete instead to cancel")
        
    if tp.status != "pending":
        raise HTTPException(status_code=400, detail="Partnership is not pending")
        
    tp.status = "rejected"
    db.commit()
    db.refresh(tp)
    return tp

@router.delete("/{id}")
def revoke_partnership(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity_id = current_user.entity_id
    tp = db.query(TradePartnership).filter(TradePartnership.id == id).first()
    if not tp:
        raise HTTPException(status_code=404, detail="Partnership not found")
        
    if tp.from_entity_id != entity_id and tp.to_entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Not a party to this partnership")
        
    db.delete(tp)
    db.commit()
    return {"message": "Partnership revoked"}
