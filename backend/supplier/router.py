import secrets
from fastapi import BackgroundTasks
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from config import settings
from models import (
    User,
    Supplier,
    Manufacturer,
    Consumer,
    Shipment,
    MedicineBatch,
    HandoffRecord,
    ApprovalLog,
    StockLevel,
    RestockRequest,
)
from auth.dependencies import require_supplier
from verification_ai.wiring import trigger_verification_and_blockchain
from supplier.schemas import (
    IncomingShipmentItem,
    ShipmentVerifyRequest,
    ShipmentVerifyResponse,
    InventoryItem,
    InventoryUpdateRequest,
    DispatchableBatchItem,
    OutboundShipmentCreate,
    OutboundShipmentResponse,
    RestockRequestCreate,
    RestockRequestResponse,
)
from supplier.batch_inventory import (
    received_units_for_batch,
    outbound_dispatched_for_batch,
    remaining_units_for_batch,
)
from qr_service.generator import generate_shipment_qr
from shared.schemas import EmergencyNotificationItem
from shared.emergency_notifications import (
    notifications_for_supplier,
    to_notification_items,
)
from auth.signing import sign_handoff
from auth.zkp import generate_salt, create_commitment

router = APIRouter(prefix="/supplier", tags=["Supplier"])


def _get_supplier(db: Session, entity_id: str) -> Supplier:
    supplier = db.query(Supplier).filter(Supplier.id == entity_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier record not found for this user",
        )
    return supplier


def _write_approval_log(
    db: Session,
    user: User,
    action_type: str,
    entity_id: str,
    entity_type: str,
    notes: str,
    signed_payload: dict = None,
) -> ApprovalLog:
    signature = None
    if signed_payload and user.private_key_pem:
        signature = sign_handoff(user.private_key_pem, signed_payload)

    log = ApprovalLog(
        actor_role=user.sub_role,
        actor_name=user.full_name or user.email,
        actor_id=user.id,
        action_type=action_type,
        entity_id=entity_id,
        entity_type=entity_type,
        notes=notes,
        signature=signature,
        signer_address=user.public_key_pem,
    )
    db.add(log)
    return log


def _upsert_stock(
    db: Session,
    entity_id: str,
    entity_type: str,
    medicine_name: str,
    quantity_to_add: int,
    reorder_threshold: Optional[int] = None,
) -> StockLevel:
    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == entity_id,
            StockLevel.entity_type == entity_type,
            StockLevel.medicine_name == medicine_name,
        )
        .first()
    )
    if stock:
        stock.quantity += quantity_to_add
        if reorder_threshold is not None:
            stock.reorder_threshold = reorder_threshold
    else:
        stock = StockLevel(
            entity_id=entity_id,
            entity_type=entity_type,
            medicine_name=medicine_name,
            quantity=quantity_to_add,
            reorder_threshold=reorder_threshold or 1000,
        )
        db.add(stock)
    db.flush()
    return stock


@router.get("/shipments/incoming", response_model=List[IncomingShipmentItem])
def list_incoming_shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)
    rows = (
        db.query(Shipment, MedicineBatch)
        .join(MedicineBatch, Shipment.batch_id == MedicineBatch.id)
        .filter(Shipment.to_entity_id == supplier.id)
        .order_by(Shipment.created_at.desc())
        .all()
    )
    return [
        IncomingShipmentItem(
            id=shipment.id,
            shipment_code=shipment.shipment_code,
            batch_id=shipment.batch_id,
            medicine_name=batch.name,
            batch_number=batch.batch_number,
            quantity_dispatched=shipment.quantity_dispatched,
            status=shipment.status,
            from_entity_id=shipment.from_entity_id,
            created_at=shipment.created_at,
        )
        for shipment, batch in rows
    ]


@router.post(
    "/shipments/{shipment_id}/verify",
    response_model=ShipmentVerifyResponse,
    status_code=status.HTTP_200_OK,
)
def verify_incoming_shipment(
    shipment_id: str,
    data: ShipmentVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)

    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id, Shipment.to_entity_id == supplier.id)
        .first()
    )
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found or not assigned to your warehouse",
        )

    if shipment.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment already verified and received",
        )

    existing_handoff = (
        db.query(HandoffRecord)
        .filter(
            HandoffRecord.shipment_id == shipment.id,
            HandoffRecord.stage == "supplier_receipt",
        )
        .first()
    )
    if existing_handoff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier verification already submitted for this shipment",
        )

    batch = db.query(MedicineBatch).filter(MedicineBatch.id == shipment.batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    salt = generate_salt()
    commitment = create_commitment(data.quantity_reported, salt)

    handoff = HandoffRecord(
        shipment_id=shipment.id,
        stage="supplier_receipt",
        submitted_by_role=current_user.sub_role,
        quantity_reported=data.quantity_reported,
        quantity_commitment=commitment,
        quantity_salt=salt,
        expiry_reported=data.expiry_reported,
        temp_reported=data.temp_reported,
    )
    db.add(handoff)
    db.flush()

    shipment.status = "delivered"
    stock = _upsert_stock(
        db,
        entity_id=supplier.id,
        entity_type="supplier",
        medicine_name=batch.name,
        quantity_to_add=data.quantity_reported,
    )

    notes = (
        data.notes
        or f"Verified receipt of {batch.name} ({batch.batch_number}) · "
        f"{data.quantity_reported} units · shipment {shipment.shipment_code}"
    )

    signed_payload = {
        "action": "incoming_verification",
        "shipment_id": shipment.id,
        "quantity_commitment": commitment,
        "supplier_id": supplier.id,
    }

    approval_log = _write_approval_log(
        db,
        current_user,
        action_type="incoming_verification",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=notes,
        signed_payload=signed_payload,
    )
    db.commit()
    db.refresh(handoff)
    db.refresh(approval_log)

    # Trigger three-party verification AI + blockchain (non-blocking)
    verification_result = trigger_verification_and_blockchain(
        shipment_id=shipment.id,
        db=db,
        background_tasks=background_tasks,
    )
    db.commit()  # persist AIFlag

    return ShipmentVerifyResponse(
        shipment_id=shipment.id,
        handoff_id=handoff.id,
        status=shipment.status,
        approval_log_id=approval_log.id,
        stock_level_id=stock.id,
        ai_status=verification_result.get("status"),
        ai_risk_score=verification_result.get("risk_score"),
        ai_explanation=verification_result.get("explanation"),
    )


@router.get("/batches/dispatchable", response_model=List[DispatchableBatchItem])
def list_dispatchable_batches(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)
    received_rows = (
        db.query(Shipment.batch_id)
        .filter(
            Shipment.to_entity_id == supplier.id,
            Shipment.status == "delivered",
        )
        .distinct()
        .all()
    )
    items: List[DispatchableBatchItem] = []
    for (batch_id,) in received_rows:
        batch = db.query(MedicineBatch).filter(MedicineBatch.id == batch_id).first()
        if not batch:
            continue
        received = received_units_for_batch(db, batch, supplier.id)
        dispatched = outbound_dispatched_for_batch(db, batch, supplier.id)
        remaining = remaining_units_for_batch(db, batch, supplier.id)
        if remaining <= 0:
            continue
        items.append(
            DispatchableBatchItem(
                batch_id=batch.id,
                medicine_name=batch.name,
                batch_number=batch.batch_number,
                quantity_received=received,
                quantity_dispatched=dispatched,
                quantity_remaining=remaining,
            )
        )
    items.sort(key=lambda x: x.medicine_name)
    return items


@router.post(
    "/shipments/outbound",
    response_model=OutboundShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def dispatch_to_hospital(
    data: OutboundShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)

    batch = db.query(MedicineBatch).filter(MedicineBatch.id == data.batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if received_units_for_batch(db, batch, supplier.id) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch not received at your warehouse yet — verify incoming shipment first",
        )

    remaining = remaining_units_for_batch(db, batch, supplier.id)
    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No units remaining to dispatch for this batch",
        )
    if data.quantity > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot dispatch {data.quantity} units; only {remaining} remaining",
        )

    hospital = db.query(Consumer).filter(Consumer.id == data.to_entity_id).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital/NGO not found",
        )

    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == supplier.id,
            StockLevel.entity_type == "supplier",
            StockLevel.medicine_name == batch.name,
        )
        .first()
    )
    if stock and stock.quantity < data.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Warehouse stock ({stock.quantity}) is less than dispatch "
                f"quantity ({data.quantity})"
            ),
        )

    shipment_code = f"SHP-OUT-{batch.batch_number}-{secrets.token_hex(3).upper()}"
    while db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first():
        shipment_code = f"SHP-OUT-{batch.batch_number}-{secrets.token_hex(3).upper()}"

    shipment = Shipment(
        batch_id=batch.id,
        from_entity_id=supplier.id,
        to_entity_id=hospital.id,
        shipment_code=shipment_code,
        quantity_dispatched=data.quantity,
        status="pending",
    )
    db.add(shipment)
    db.flush()

    if stock:
        stock.quantity -= data.quantity

    qr_path = generate_shipment_qr(shipment.id)
    shipment.qr_code_url = qr_path

    signed_payload = {
        "action": "shipment_dispatch",
        "batch_id": batch.id,
        "shipment_code": shipment_code,
        "quantity_dispatched": data.quantity,
        "to_entity_id": hospital.id,
    }

    approval_log = _write_approval_log(
        db,
        current_user,
        action_type="shipment_dispatch",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=(
            f"Dispatched {data.quantity} units of {batch.name} ({batch.batch_number}) "
            f"to {hospital.name} · code {shipment_code} · "
            f"{remaining - data.quantity} units remaining for this batch"
        ),
        signed_payload=signed_payload,
    )
    db.commit()
    db.refresh(shipment)
    db.refresh(approval_log)

    return OutboundShipmentResponse(
        id=shipment.id,
        batch_id=shipment.batch_id,
        from_entity_id=shipment.from_entity_id,
        to_entity_id=shipment.to_entity_id,
        shipment_code=shipment.shipment_code,
        quantity_dispatched=shipment.quantity_dispatched,
        qr_code_url=f"{settings.API_BASE_URL}{qr_path}",
        verification_url=f"{settings.PUBLIC_APP_URL}/shared/shipment/{shipment.id}",
        status=shipment.status,
        approval_log_id=approval_log.id,
    )


@router.get("/inventory", response_model=List[InventoryItem])
def list_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)
    items = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == supplier.id,
            StockLevel.entity_type == "supplier",
        )
        .order_by(StockLevel.medicine_name)
        .all()
    )
    return items


@router.put("/inventory", response_model=InventoryItem)
def update_inventory(
    data: InventoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)
    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == supplier.id,
            StockLevel.entity_type == "supplier",
            StockLevel.medicine_name == data.medicine_name,
        )
        .first()
    )
    if stock:
        stock.quantity = data.quantity
        if data.reorder_threshold is not None:
            stock.reorder_threshold = data.reorder_threshold
    else:
        stock = StockLevel(
            entity_id=supplier.id,
            entity_type="supplier",
            medicine_name=data.medicine_name,
            quantity=data.quantity,
            reorder_threshold=data.reorder_threshold or 1000,
        )
        db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.post(
    "/restock-requests",
    response_model=RestockRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_restock_request(
    data: RestockRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)

    manufacturer = (
        db.query(Manufacturer).filter(Manufacturer.id == data.target_entity_id).first()
    )
    if not manufacturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target manufacturer not found",
        )

    request = RestockRequest(
        requester_entity_id=supplier.id,
        requester_type="supplier",
        target_entity_id=manufacturer.id,
        medicine_name=data.medicine_name,
        quantity_requested=data.quantity_requested,
        reason=data.reason,
        urgency=data.urgency,
        status="pending",
    )
    db.add(request)
    db.flush()

    approval_log = _write_approval_log(
        db,
        current_user,
        action_type="emergency_restock",
        entity_id=request.id,
        entity_type="restock_request",
        notes=(
            f"Emergency restock to {manufacturer.name}: "
            f"{data.medicine_name} × {data.quantity_requested} · {data.reason}"
        ),
    )
    db.commit()
    db.refresh(request)
    db.refresh(approval_log)

    return RestockRequestResponse(
        id=request.id,
        requester_entity_id=request.requester_entity_id,
        target_entity_id=request.target_entity_id,
        medicine_name=request.medicine_name,
        quantity_requested=request.quantity_requested,
        reason=request.reason,
        urgency=request.urgency,
        status=request.status,
        approval_log_id=approval_log.id,
    )


@router.get("/emergency-notifications", response_model=List[EmergencyNotificationItem])
def list_emergency_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    supplier = _get_supplier(db, current_user.entity_id)
    requests = notifications_for_supplier(db, supplier.id)
    return to_notification_items(db, requests)
