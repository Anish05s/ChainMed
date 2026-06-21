from pydantic import BaseModel, ValidationError
from datetime import datetime
from typing import Optional

class ShipmentVerifyRequest(BaseModel):
    quantity_reported: int
    expiry_reported: datetime
    temp_reported: Optional[float] = None
    notes: Optional[str] = None

try:
    ShipmentVerifyRequest(
        quantity_reported=2000,
        expiry_reported="20-06-2029T00:00:00",
    )
    print("SUCCESS")
except ValidationError as e:
    print("VALIDATION ERROR:", e.errors())
