from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ApprovalLogItem(BaseModel):
    id: str
    actor_role: str
    actor_name: str
    actor_id: Optional[str] = None
    action_type: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    notes: Optional[str] = None
    blockchain_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    # P1.5 — Hash chain fields
    log_hash: Optional[str] = None
    previous_hash: Optional[str] = None

    class Config:
        from_attributes = True
