from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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
    active_override_request_id: Optional[str] = None

class OverrideRequest(BaseModel):
    justification: str

class OverrideVoteRequest(BaseModel):
    vote: str  # "approve" | "reject"

class AdminOverrideVoteResponse(BaseModel):
    id: str
    admin_id: str
    admin_name: str
    admin_sub_role: str
    vote: str
    created_at: datetime

class OverrideRequestResponse(BaseModel):
    id: str
    shipment_id: str
    initiated_by: str
    justification: str
    status: str
    required_approvals: int
    current_approvals: int
    override_blockchain_hash: Optional[str] = None
    ai_cross_check: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None
    
    votes: Optional[List[AdminOverrideVoteResponse]] = []
