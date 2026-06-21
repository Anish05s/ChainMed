from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ApprovalLogItem(BaseModel):
    id: str
    actor_role: str
    actor_name: str
    action_type: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    notes: Optional[str] = None
    blockchain_hash: Optional[str] = None
    created_at: datetime
    # P1.5 — Hash chain fields
    log_hash: Optional[str] = None
    previous_hash: Optional[str] = None

    class Config:
        from_attributes = True


class HandoffPublicItem(BaseModel):
    stage: str
    submitted_by_role: str
    quantity_reported: Optional[int] = None
    temp_reported: Optional[float] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


class EmergencyNotificationItem(BaseModel):
    id: str
    requester_type: str
    requester_name: str
    target_entity_id: str
    target_name: str
    medicine_name: str
    quantity_requested: int
    reason: str
    urgency: str
    status: str
    created_at: datetime


class OverrideSummary(BaseModel):
    justification: str
    ai_cross_check: Optional[str] = None
    approvers: List[str]

class PublicShipmentResponse(BaseModel):
    id: str
    shipment_code: str
    status: str
    created_at: datetime
    batch_name: str
    batch_number: str
    medicine_quantity: int
    expiry_date: datetime
    from_entity_name: str
    to_entity_name: str
    qr_code_url: Optional[str] = None
    blockchain_hash: Optional[str] = None
    override_blockchain_hash: Optional[str] = None
    override_details: Optional[OverrideSummary] = None
    handoffs: List[HandoffPublicItem] = []
    approval_logs: List[ApprovalLogItem] = []

class MedicineCatalogItem(BaseModel):
    id: str
    medicine_name: str
    pack_size_label: str
    created_at: datetime

    class Config:
        from_attributes = True
