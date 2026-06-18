from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class BatchCreateRequest(BaseModel):
    name: str
    batch_number: str = Field(..., min_length=1)
    medicine_type: Optional[str] = None
    pack_size: Optional[str] = None
    number_of_packs: Optional[int] = None
    pieces_per_pack: int = Field(1, gt=0)
    quantity: int = Field(..., gt=0)
    expiry_date: datetime
    manufacturing_date: datetime
    storage_temp_declared: Optional[float] = None


class BatchResponse(BaseModel):
    id: str
    manufacturer_id: str
    name: str
    batch_number: str
    quantity: int
    expiry_date: datetime
    manufacturing_date: datetime
    storage_temp_declared: Optional[float] = None
    approval_log_id: str

    class Config:
        from_attributes = True


class BatchListItem(BaseModel):
    id: str
    name: str
    batch_number: str
    quantity: int
    quantity_dispatched: int = 0
    quantity_remaining: int
    expiry_date: datetime
    manufacturing_date: datetime
    storage_temp_declared: Optional[float] = None
    pieces_per_pack: int = 1
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShipmentCreateRequest(BaseModel):
    batch_id: str
    to_entity_id: str
    quantity: int = Field(..., gt=0)


class ShipmentResponse(BaseModel):
    id: str
    batch_id: str
    from_entity_id: str
    to_entity_id: str
    shipment_code: str
    quantity_dispatched: int
    qr_code_url: str
    verification_url: str
    status: str
    approval_log_id: str

    class Config:
        from_attributes = True
