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
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReceiptConfirmRequest(BaseModel):
    quantity_reported: int = Field(..., gt=0)
    expiry_reported: datetime
    temp_reported: Optional[float] = None
    notes: Optional[str] = None


class ReceiptConfirmResponse(BaseModel):
    shipment_id: str
    handoff_id: str
    status: str
    approval_log_id: str
    stock_level_id: Optional[str] = None
    ai_status: Optional[str] = None
    ai_risk_score: Optional[float] = None
    ai_explanation: Optional[str] = None


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


class StockRequestCreate(BaseModel):
    medicine_name: str
    quantity_requested: int
    reason: str
    urgency: str = "normal"


class StockRequestResponse(BaseModel):
    id: str
    requester_entity_id: str
    target_entity_id: str
    medicine_name: str
    quantity_requested: int
    reason: str
    urgency: str
    status: str
    approval_log_id: str

    class Config:
        from_attributes = True


CLEARANCE_REASONS = (
    "patient_dispensed",
    "expired",
    "damaged",
    "recalled",
    "transfer",
    "other",
)


class StockClearanceRequest(BaseModel):
    medicine_name: str = Field(..., min_length=1)
    quantity_cleared: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    notes: Optional[str] = None


class StockClearanceResponse(BaseModel):
    stock_level_id: str
    medicine_name: str
    quantity_cleared: int
    quantity_remaining: int
    reason: str
    approval_log_id: str
    low_stock_alert: bool = False


class StockClearanceHistoryItem(BaseModel):
    id: str
    medicine_name: str
    quantity_cleared: int
    reason: str
    quantity_remaining_after: int
    notes: Optional[str] = None
    created_at: datetime
