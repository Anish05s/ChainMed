import re
from fastapi import BackgroundTasks
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from blockchain_service.service import bg_record_handoff_and_store
from models import (
    User,
    Consumer,
    Supplier,
    Shipment,
    MedicineBatch,
    HandoffRecord,
    ApprovalLog,
    StockLevel,
    RestockRequest,
)
from auth.dependencies import require_consumer
from verification_ai.wiring import trigger_verification_and_blockchain
from consumer.schemas import (
    IncomingShipmentItem,
    ReceiptConfirmRequest,
    ReceiptConfirmResponse,
    InventoryItem,
    InventoryUpdateRequest,
    StockRequestCreate,
    StockRequestResponse,
    StockClearanceRequest,
    StockClearanceResponse,
    StockClearanceHistoryItem,
    ReturnRequest,
    CLEARANCE_REASONS,
)
from auth.signing import sign_handoff
from audit_chain import write_approval_log
from auth.zkp import generate_salt, create_commitment

router = APIRouter(prefix="/consumer", tags=["Consumer"])


def _get_consumer(db: Session, entity_id: str) -> Consumer:
    consumer = db.query(Consumer).filter(Consumer.id == entity_id).first()
    if not consumer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital/NGO record not found for this user",
        )
    return consumer





def _upsert_stock(
    db: Session,
    entity_id: str,
    entity_type: str,
    medicine_name: str,
    quantity_to_add: int,
    pieces_per_pack: int = 1,
    pack_size_label: Optional[str] = None,
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
        stock.pieces_per_pack = pieces_per_pack
        if pack_size_label:
            stock.pack_size_label = pack_size_label
        if reorder_threshold is not None:
            stock.reorder_threshold = reorder_threshold
    else:
        stock = StockLevel(
            entity_id=entity_id,
            entity_type=entity_type,
            medicine_name=medicine_name,
            quantity=quantity_to_add,
            pieces_per_pack=pieces_per_pack,
            pack_size_label=pack_size_label,
            reorder_threshold=reorder_threshold or 1000,
        )
        db.add(stock)
    db.flush()
    return stock


@router.get("/shipments/incoming", response_model=List[IncomingShipmentItem])
def list_incoming_shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    from models import AdminApprovalRequest
    consumer = _get_consumer(db, current_user.entity_id)
    rows = (
        db.query(Shipment, MedicineBatch)
        .join(MedicineBatch, Shipment.batch_id == MedicineBatch.id)
        .filter(Shipment.to_entity_id == consumer.id)
        .order_by(Shipment.created_at.desc())
        .all()
    )
    
    shipment_ids = [s.id for s, b in rows]
    pending_disputes = set()
    if shipment_ids:
        disputes = db.query(AdminApprovalRequest.entity_id).filter(
            AdminApprovalRequest.entity_id.in_(shipment_ids),
            AdminApprovalRequest.entity_type == "shipment",
            AdminApprovalRequest.status == "pending"
        ).all()
        pending_disputes = {d[0] for d in disputes}

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
            has_pending_dispute=(shipment.id in pending_disputes),
        )
        for shipment, batch in rows
    ]


@router.post(
    "/shipments/{shipment_id}/confirm",
    response_model=ReceiptConfirmResponse,
)
def confirm_receipt(
    shipment_id: str,
    data: ReceiptConfirmRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)

    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id, Shipment.to_entity_id == consumer.id)
        .first()
    )
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found or not assigned to your facility",
        )

    if shipment.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already confirmed",
        )

    if (
        db.query(HandoffRecord)
        .filter(
            HandoffRecord.shipment_id == shipment.id,
            HandoffRecord.stage == "hospital_receipt",
        )
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipt already confirmed for this shipment",
        )

    batch = db.query(MedicineBatch).filter(MedicineBatch.id == shipment.batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    salt = generate_salt()
    commitment = create_commitment(data.quantity_reported, salt)

    payload_to_sign = {
        "shipment_id": shipment.id,
        "quantity_reported": data.quantity_reported,
        "quantity_commitment": commitment,
        "expiry_reported": data.expiry_reported.isoformat(),
        "temp_reported": data.temp_reported,
    }
    signature = sign_handoff(current_user.private_key_pem, payload_to_sign) if current_user.private_key_pem else None

    handoff = HandoffRecord(
        shipment_id=shipment.id,
        stage="hospital_receipt",
        submitted_by_role=current_user.sub_role,
        quantity_reported=data.quantity_reported,
        quantity_commitment=commitment,
        quantity_salt=salt,
        expiry_reported=data.expiry_reported,
        temp_reported=data.temp_reported,
        signature=signature,
        public_key_pem=current_user.public_key_pem,
    )
    db.add(handoff)
    db.flush()

    shipment.status = "delivered"
    stock = _upsert_stock(
        db,
        entity_id=consumer.id,
        entity_type="consumer",
        medicine_name=batch.name,
        quantity_to_add=data.quantity_reported,
        pieces_per_pack=batch.pieces_per_pack,
        pack_size_label=batch.pack_size,
    )

    notes = (
        data.notes
        or f"Confirmed receipt at {consumer.name}: {batch.name} ({batch.batch_number}) · "
        f"{data.quantity_reported} units · {shipment.shipment_code}"
    )

    signed_payload = {
        "action": "receipt_confirmation",
        "shipment_id": shipment.id,
        "quantity_commitment": commitment,
        "consumer_id": consumer.id,
    }

    approval_log = write_approval_log(
        db,
        current_user,
        action_type="receipt_confirmation",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=notes,
        signed_payload=signed_payload,
    )
    db.commit()
    db.refresh(handoff)
    db.refresh(approval_log)

    # Auto-resolve any pending emergency restock requests for this medicine
    pending_request = (
        db.query(RestockRequest)
        .filter(
            RestockRequest.requester_entity_id == consumer.id,
            RestockRequest.requester_type == "consumer",
            RestockRequest.medicine_name == batch.name,
            RestockRequest.status == "pending"
        )
        .first()
    )
    if pending_request:
        pending_request.status = "resolved"
        # Append a note to the approval log that it resolved an emergency
        approval_log.notes = str(approval_log.notes) + f" [Auto-resolved Emergency Request for {batch.name}]"
        db.commit()

    # Trigger three-party verification AI + blockchain (non-blocking)
    # For hospital_receipt we need to find the inbound shipment from supplier
    verification_result = trigger_verification_and_blockchain(
        shipment_id=shipment.id,
        db=db,
        background_tasks=background_tasks,
        hospital_shipment_id=shipment.id,
        approval_log_id=approval_log.id,
    )
    db.commit()  # persist AIFlag

    return ReceiptConfirmResponse(
        shipment_id=shipment.id,
        handoff_id=handoff.id,
        status=shipment.status,
        approval_log_id=approval_log.id,
        stock_level_id=stock.id,
        ai_status=verification_result.get("status"),
        ai_risk_score=verification_result.get("risk_score"),
        ai_explanation=verification_result.get("explanation"),
    )

import secrets

@router.post("/shipments/{shipment_id}/return", status_code=status.HTTP_201_CREATED)
def return_shipment(
    shipment_id: str,
    data: ReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)
    
    original_shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id, Shipment.to_entity_id == consumer.id)
        .first()
    )
    if not original_shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    if original_shipment.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered shipments can be returned")
        
    batch = db.query(MedicineBatch).filter(MedicineBatch.id == original_shipment.batch_id).first()
    
    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == consumer.id,
            StockLevel.entity_type == "consumer",
            StockLevel.medicine_name == batch.name,
        )
        .first()
    )
    
    if not stock or stock.quantity < data.quantity_returned:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient stock to return. Have {stock.quantity if stock else 0}, trying to return {data.quantity_returned}"
        )
        
    stock.quantity -= data.quantity_returned
    
    shipment_code = f"RET-{batch.batch_number}-{secrets.token_hex(3).upper()}"
    while db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first():
        shipment_code = f"RET-{batch.batch_number}-{secrets.token_hex(3).upper()}"
        
    return_shipment = Shipment(
        batch_id=batch.id,
        from_entity_id=consumer.id,
        to_entity_id=original_shipment.from_entity_id,
        shipment_code=shipment_code,
        quantity_dispatched=data.quantity_returned,
        status="return_pending",
    )
    db.add(return_shipment)
    db.flush()
    
    approval_log = write_approval_log(
        db,
        current_user,
        action_type="shipment_return",
        entity_id=return_shipment.id,
        entity_type="shipment",
        notes=f"Returned {data.quantity_returned} units of {batch.name} to supplier. Reason: {data.reason}",
    )
    db.commit()
    
    return {
        "status": "return_pending",
        "return_shipment_id": return_shipment.id,
        "shipment_code": return_shipment.shipment_code,
        "quantity_returned": return_shipment.quantity_dispatched,
    }


@router.get("/inventory", response_model=List[InventoryItem])
def list_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)
    return (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == consumer.id,
            StockLevel.entity_type == "consumer",
        )
        .order_by(StockLevel.medicine_name)
        .all()
    )


@router.put("/inventory", response_model=InventoryItem)
def update_inventory(
    data: InventoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)
    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == consumer.id,
            StockLevel.entity_type == "consumer",
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
            entity_id=consumer.id,
            entity_type="consumer",
            medicine_name=data.medicine_name,
            quantity=data.quantity,
            reorder_threshold=data.reorder_threshold or 500,
        )
        db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.post(
    "/inventory/clearance",
    response_model=StockClearanceResponse,
    status_code=status.HTTP_200_OK,
)
def clear_stock(
    data: StockClearanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)

    if data.reason not in CLEARANCE_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reason must be one of: {', '.join(CLEARANCE_REASONS)}",
        )

    stock = (
        db.query(StockLevel)
        .filter(
            StockLevel.entity_id == consumer.id,
            StockLevel.entity_type == "consumer",
            StockLevel.medicine_name == data.medicine_name,
        )
        .first()
    )
    if not stock or stock.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stock found for this medicine at your facility",
        )
    if data.quantity_cleared > stock.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot clear {data.quantity_cleared} units; "
                f"only {stock.quantity} in stock"
            ),
        )

    stock.quantity -= data.quantity_cleared
    remaining = stock.quantity
    reason_label = data.reason.replace("_", " ")

    log_notes = (
        f"Stock clearance at {consumer.name}: {data.medicine_name} · "
        f"cleared {data.quantity_cleared} units ({reason_label}) · "
        f"{remaining} units remaining"
    )
    if data.notes:
        log_notes += f" · {data.notes}"

    approval_log = write_approval_log(
        db,
        current_user,
        action_type="stock_clearance",
        entity_id=stock.id,
        entity_type="stock_level",
        notes=log_notes,
    )
    db.commit()
    db.refresh(stock)
    db.refresh(approval_log)

    return StockClearanceResponse(
        stock_level_id=stock.id,
        medicine_name=stock.medicine_name,
        quantity_cleared=data.quantity_cleared,
        quantity_remaining=remaining,
        reason=data.reason,
        approval_log_id=approval_log.id,
        low_stock_alert=remaining <= stock.reorder_threshold,
    )


@router.get("/inventory/clearances", response_model=List[StockClearanceHistoryItem])
def list_stock_clearances(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
    limit: int = 30,
):
    logs = (
        db.query(ApprovalLog)
        .filter(
            ApprovalLog.action_type == "stock_clearance",
            ApprovalLog.actor_id == current_user.id,
        )
        .order_by(ApprovalLog.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    items: List[StockClearanceHistoryItem] = []
    for log in logs:
        parsed = _parse_clearance_log(log.notes or "")
        if not parsed:
            continue
        items.append(
            StockClearanceHistoryItem(
                id=log.id,
                medicine_name=parsed["medicine_name"],
                quantity_cleared=parsed["quantity_cleared"],
                reason=parsed["reason"],
                quantity_remaining_after=parsed["remaining"],
                notes=parsed.get("user_notes"),
                created_at=log.created_at,
            )
        )
    return items


def _parse_clearance_log(notes: str) -> Optional[dict]:
    """Parse approval log notes from clear_stock."""
    m = re.search(
        r":\s*(.+?)\s*·\s*cleared\s+(\d+)\s+units\s+\(([^)]+)\)\s*·\s*(\d+)\s+units remaining",
        notes,
    )
    if not m:
        return None
    reason_raw = m.group(3).replace(" ", "_")
    user_notes = None
    if " · " in notes:
        parts = notes.split(" · ")
        if len(parts) > 4:
            user_notes = parts[-1]
    return {
        "medicine_name": m.group(1).strip(),
        "quantity_cleared": int(m.group(2)),
        "reason": reason_raw,
        "remaining": int(m.group(4)),
        "user_notes": user_notes,
    }


from shared.dijkstra import find_best_restock_route

@router.post(
    "/stock-requests",
    response_model=StockRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_request(
    data: StockRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)

    # Use Dijkstra to find the best supplier
    route = find_best_restock_route(db, consumer.id, "consumer", data.medicine_name, data.quantity_requested)
    
    if not route or len(route) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered supplier found with sufficient stock in the network."
        )
        
    # The direct target is the next hop in the route (route[1])
    target_supplier_id = route[1]
    supplier = db.query(Supplier).filter(Supplier.id == target_supplier_id).first()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Resolved supplier not found")

    request = RestockRequest(
        requester_entity_id=consumer.id,
        requester_type="consumer",
        target_entity_id=supplier.id,
        medicine_name=data.medicine_name,
        quantity_requested=data.quantity_requested,
        reason=data.reason,
        urgency=data.urgency,
        status="pending",
    )
    db.add(request)
    db.flush()

    # If the route is longer than 2, it means the supplier will likely need to restock from manufacturer
    route_note = ""
    if len(route) > 2:
        route_note = " (System notes: Supplier may need to source from Manufacturer)"

    approval_log = write_approval_log(
        db,
        current_user,
        action_type="emergency_stock_request",
        entity_id=request.id,
        entity_type="restock_request",
        notes=(
            f"Emergency stock request routed via Dijkstra to {supplier.name}: "
            f"{data.medicine_name} × {data.quantity_requested} · {data.reason}{route_note}"
        ),
    )
    db.commit()
    db.refresh(request)
    db.refresh(approval_log)

    return StockRequestResponse(
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


@router.get("/restock-requests/mine", response_model=List[StockRequestResponse])
def get_my_restock_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)
    requests = (
        db.query(RestockRequest)
        .filter(
            RestockRequest.requester_entity_id == consumer.id,
            RestockRequest.requester_type == "consumer",
        )
        .order_by(RestockRequest.created_at.desc())
        .all()
    )
    return [
        StockRequestResponse(
            id=r.id,
            requester_entity_id=r.requester_entity_id,
            target_entity_id=r.target_entity_id,
            medicine_name=r.medicine_name,
            quantity_requested=r.quantity_requested,
            reason=r.reason,
            urgency=r.urgency,
            status=r.status,
            approval_log_id=None,
        )
        for r in requests
    ]


@router.post("/restock-requests/{request_id}/resolve")
def resolve_restock_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_consumer),
):
    consumer = _get_consumer(db, current_user.entity_id)
    
    req = db.query(RestockRequest).filter(RestockRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.requester_entity_id != consumer.id or req.requester_type != "consumer":
        raise HTTPException(status_code=403, detail="Not authorized to resolve this request")
        
    if req.status == "resolved":
        return {"status": "already_resolved"}
        
    req.status = "resolved"
    db.commit()
    return {"status": "resolved"}
