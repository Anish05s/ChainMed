from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
import datetime
import enum

def gen_uuid():
    return str(uuid.uuid4())

def now():
    return datetime.datetime.utcnow()

# --- ENUMS ---
class UserRole(str, enum.Enum):
    manufacturer = "manufacturer"
    supplier = "supplier"
    consumer = "consumer"
    admin = "admin"

class SubRole(str, enum.Enum):
    manufacturer_admin = "manufacturer_admin"
    supplier_manager = "supplier_manager"
    hospital_officer = "hospital_officer"
    admin_master = "admin_master"
    admin_manager = "admin_manager"
    admin_dev = "admin_dev"

class ShipmentStatus(str, enum.Enum):
    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"

class VerificationStatus(str, enum.Enum):
    verified = "VERIFIED"
    flagged = "FLAGGED"
    pending = "PENDING"

class RestockStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    fulfilled = "fulfilled"

# --- TABLES ---
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, nullable=False)
    sub_role = Column(String, nullable=False)
    entity_id = Column(String)
    public_key_pem = Column(Text, nullable=True)
    private_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)

class Manufacturer(Base):
    __tablename__ = "manufacturers"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    license_number = Column(String, unique=True)
    country = Column(String)
    trust_score = Column(Float, default=100.0)
    public_key_pem = Column(Text, nullable=True)
    private_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    warehouse_location = Column(String)
    country = Column(String)
    trust_score = Column(Float, default=100.0)
    public_key_pem = Column(Text, nullable=True)
    private_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)

class Consumer(Base):
    __tablename__ = "consumers"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    type = Column(String)
    location = Column(String)
    country = Column(String)
    trust_score = Column(Float, default=100.0)
    public_key_pem = Column(Text, nullable=True)
    private_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)

class TradePartnership(Base):
    """
    Defines a registered partnership between two entities (e.g. Manufacturer->Supplier or Supplier->Consumer).
    Used for Dijkstra network pathfinding.
    """
    __tablename__ = "trade_partnerships"
    id = Column(String, primary_key=True, default=gen_uuid)
    from_entity_id = Column(String, nullable=False) # The one supplying
    to_entity_id = Column(String, nullable=False)   # The one receiving
    from_entity_type = Column(String, nullable=False) # 'manufacturer' or 'supplier'
    to_entity_type = Column(String, nullable=False)   # 'supplier' or 'consumer'
    requested_by = Column(String, nullable=True)      # the entity_id that initiated the request
    status = Column(String, default="pending")        # pending, active, rejected
    latency_days = Column(Integer, default=1) # The "weight" for Dijkstra
    created_at = Column(DateTime, default=now)


class MedicineCatalog(Base):
    __tablename__ = "medicine_catalog"
    id = Column(String, primary_key=True, default=gen_uuid)
    medicine_name = Column(String, nullable=False, index=True)
    pack_size_label = Column(String, nullable=False)
    created_at = Column(DateTime, default=now)

class MedicineBatch(Base):
    __tablename__ = "medicine_batches"
    id = Column(String, primary_key=True, default=gen_uuid)
    manufacturer_id = Column(String, ForeignKey("manufacturers.id"))
    name = Column(String, nullable=False)
    batch_number = Column(String, unique=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    # New fields for breakdown
    medicine_type = Column(String, nullable=True)
    pack_size = Column(String, nullable=True)
    number_of_packs = Column(Integer, nullable=True)
    pieces_per_pack = Column(Integer, default=1)
    expiry_date = Column(DateTime, nullable=False)
    manufacturing_date = Column(DateTime, nullable=False)
    storage_temp_declared = Column(Float)
    blockchain_hash = Column(String)
    created_at = Column(DateTime, default=now)

class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(String, primary_key=True, default=gen_uuid)
    batch_id = Column(String, ForeignKey("medicine_batches.id"))
    from_entity_id = Column(String)
    to_entity_id = Column(String)
    shipment_code = Column(String, unique=True)
    qr_code_url = Column(String)
    status = Column(String, default="pending")
    quantity_dispatched = Column(Integer, nullable=True)
    blockchain_hash = Column(String, nullable=True)
    override_blockchain_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class HandoffRecord(Base):
    __tablename__ = "handoff_records"
    id = Column(String, primary_key=True, default=gen_uuid)
    shipment_id = Column(String, ForeignKey("shipments.id"))
    stage = Column(String)
    submitted_by_role = Column(String)
    quantity_reported = Column(Integer)
    quantity_commitment = Column(String)
    quantity_salt = Column(String)
    expiry_reported = Column(DateTime)
    temp_reported = Column(Float)
    signature = Column(Text, nullable=True)
    public_key_pem = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=now)

class AIFlag(Base):
    __tablename__ = "ai_flags"
    id = Column(String, primary_key=True, default=gen_uuid)
    shipment_id = Column(String, ForeignKey("shipments.id"))
    risk_score = Column(Float)
    status = Column(String, default="PENDING")
    triggered_rules = Column(Text)
    mismatch_details = Column(Text)
    explanation = Column(Text)
    created_at = Column(DateTime, default=now)

class StockLevel(Base):
    __tablename__ = "stock_levels"
    id = Column(String, primary_key=True, default=gen_uuid)
    entity_id = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    medicine_name = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    pieces_per_pack = Column(Integer, default=1)
    pack_size_label = Column(String, nullable=True)
    reorder_threshold = Column(Integer, default=1000)
    last_updated = Column(DateTime, default=now)

class RestockRequest(Base):
    __tablename__ = "restock_requests"
    id = Column(String, primary_key=True, default=gen_uuid)
    requester_entity_id = Column(String)
    requester_type = Column(String)
    target_entity_id = Column(String)
    medicine_name = Column(String)
    quantity_requested = Column(Integer)
    reason = Column(Text)
    urgency = Column(String, default="normal")
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=now)

class DisruptionEvent(Base):
    """
    Addition 7 — Disruption Events Table
    Stores supply chain disruptions detected by crisis_ai module.
    Used for route rerouting recommendations and emergency restock triggers.
    """
    __tablename__ = "disruption_events"
    id = Column(String, primary_key=True, default=gen_uuid)
    event_type = Column(String)           # e.g. "flood", "strike", "pandemic"
    region = Column(String)               # e.g. "Maharashtra, India"
    severity = Column(String)            # "low", "medium", "high", "critical"
    description = Column(Text)           # Human-readable disruption detail
    affected_routes = Column(Text)       # JSON array of affected route IDs/names
    recommended_medicines = Column(Text) # JSON array of critical medicines to reroute
    source = Column(String, default="news_api")  # "news_api", "manual", "sensor"
    resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime, default=now)
    resolved_at = Column(DateTime, nullable=True)

class ApprovalLog(Base):
    __tablename__ = "approval_logs"
    id = Column(String, primary_key=True, default=gen_uuid)
    actor_role = Column(String, nullable=False)
    actor_name = Column(String, nullable=False)
    actor_id = Column(String)
    action_type = Column(String, nullable=False)
    entity_id = Column(String)
    entity_type = Column(String)
    notes = Column(Text)
    signature = Column(Text)
    signer_address = Column(String)
    created_at = Column(DateTime, default=now)
    blockchain_hash = Column(String)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=gen_uuid)
    recipient_id = Column(String)
    type = Column(String)
    title = Column(String)
    message = Column(Text)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


# --- Multi-Sig Admin Override ---
class AdminOverrideRequest(Base):
    """Multi-sig override request. Requires 80% of eligible admins to approve."""
    __tablename__ = "admin_override_requests"
    id = Column(String, primary_key=True, default=gen_uuid)
    shipment_id = Column(String, ForeignKey("shipments.id"), nullable=False)
    initiated_by = Column(String, ForeignKey("users.id"), nullable=False)
    justification = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending | approved | rejected | executed
    required_approvals = Column(Integer, nullable=False)
    current_approvals = Column(Integer, default=0)
    override_blockchain_hash = Column(String, nullable=True)
    ai_cross_check = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    executed_at = Column(DateTime, nullable=True)

class AdminOverrideVote(Base):
    """Individual admin vote on an override request."""
    __tablename__ = "admin_override_votes"
    id = Column(String, primary_key=True, default=gen_uuid)
    override_request_id = Column(String, ForeignKey("admin_override_requests.id"), nullable=False)
    admin_id = Column(String, ForeignKey("users.id"), nullable=False)
    admin_name = Column(String, nullable=False)
    admin_sub_role = Column(String, nullable=False)
    vote = Column(String, nullable=False)  # approve | reject
    signature = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)