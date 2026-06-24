from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class IncomingShipmentItem(BaseModel):
    id: str
    shipment_code: str
    batch_id: str
    medicine_name: str
    batch_number: str
    quantity_dispatched: Optional[int] = None
    status: str
    from_entity_id: str
    pieces_per_pack: int = 1
    pack_size: Optional[str] = None
    created_at: Optional[datetime] = None
    has_pending_dispute: bool = False

    class Config:
        from_attributes = True


class ShipmentVerifyRequest(BaseModel):
    quantity_reported: int = Field(..., gt=0)
    expiry_reported: datetime
    temp_reported: Optional[float] = None
    notes: Optional[str] = None


class ShipmentVerifyResponse(BaseModel):
    shipment_id: str
    handoff_id: str
    status: str
    approval_log_id: str
    stock_level_id: Optional[str] = None
    ai_status: Optional[str] = None
    ai_risk_score: Optional[float] = None
    ai_explanation: Optional[str] = None


class StockClearanceHistoryItem(BaseModel):
    id: str
    medicine_name: str
    quantity_cleared: int
    reason: str
    quantity_remaining_after: int
    notes: Optional[str] = None
    created_at: datetime


class ReturnRequest(BaseModel):
    quantity_returned: int = Field(..., gt=0)
    reason: str = Field(...)


class InventoryItem(BaseModel):
    id: str
    medicine_name: str
    quantity: int
    pieces_per_pack: int = 1
    pack_size_label: Optional[str] = None
    reorder_threshold: int
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class InventoryUpdateRequest(BaseModel):
    medicine_name: str
    quantity: int = Field(..., ge=0)
    reorder_threshold: Optional[int] = Field(None, ge=0)


class RestockRequestCreate(BaseModel):
    medicine_name: str
    quantity_requested: int
    reason: str
    urgency: str = "normal"


class DispatchableBatchItem(BaseModel):
    batch_id: str
    medicine_name: str
    batch_number: str
    quantity_received: int
    quantity_dispatched: int
    quantity_remaining: int
    pieces_per_pack: int = 1
    pack_size: Optional[str] = None


class OutboundShipmentCreate(BaseModel):
    batch_id: str
    to_entity_id: str
    quantity: int = Field(..., gt=0)


class OutboundShipmentResponse(BaseModel):
    id: str
    batch_id: str
    from_entity_id: str
    to_entity_id: str
    shipment_code: str
    quantity_dispatched: int
    qr_code_url: str
    verification_url: str
    status: str
    approval_log_id: Optional[str] = None


class RestockRequestResponse(BaseModel):
    id: str
    requester_entity_id: str
    target_entity_id: str
    medicine_name: str
    quantity_requested: int
    reason: str
    urgency: str
    status: str
    approval_log_id: Optional[str] = None

    class Config:
        from_attributes = True
