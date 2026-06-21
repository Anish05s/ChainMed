import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from config import settings
from blockchain_service.service import bg_record_handoff_and_store
from models import Manufacturer, MedicineBatch, ApprovalLog, Shipment, Supplier, TradePartnership
from auth.dependencies import require_manufacturer
from models import User
from manufacturer.schemas import (
    BatchCreateRequest,
    BatchResponse,
    BatchListItem,
    ShipmentCreateRequest,
    ShipmentResponse,
)
from auth.signing import sign_handoff
from qr_service.generator import generate_shipment_qr
from manufacturer.batch_inventory import (
    dispatched_units_for_batch,
    remaining_units_for_batch,
)
from shared.schemas import EmergencyNotificationItem
from shared.emergency_notifications import (
    notifications_for_manufacturer,
    to_notification_items,
)

router = APIRouter(prefix="/manufacturer", tags=["Manufacturer"])


def _get_manufacturer(db: Session, entity_id: str) -> Manufacturer:
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == entity_id).first()
    if not manufacturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manufacturer record not found for this user",
        )
    return manufacturer


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


@router.get("/batches", response_model=List[BatchListItem])
def list_batches(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manufacturer),
):
    manufacturer = _get_manufacturer(db, current_user.entity_id)
    batches = (
        db.query(MedicineBatch)
        .filter(MedicineBatch.manufacturer_id == manufacturer.id)
        .order_by(MedicineBatch.created_at.desc())
        .all()
    )
    return [
        BatchListItem(
            id=batch.id,
            name=batch.name,
            batch_number=batch.batch_number,
            quantity=batch.quantity,
            quantity_dispatched=dispatched_units_for_batch(db, batch, manufacturer.id),
            quantity_remaining=remaining_units_for_batch(db, batch, manufacturer.id),
            expiry_date=batch.expiry_date,
            manufacturing_date=batch.manufacturing_date,
            storage_temp_declared=batch.storage_temp_declared,
            pieces_per_pack=batch.pieces_per_pack,
            created_at=batch.created_at,
        )
        for batch in batches
    ]


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    data: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manufacturer),
):
    manufacturer = _get_manufacturer(db, current_user.entity_id)

    existing = (
        db.query(MedicineBatch)
        .filter(MedicineBatch.batch_number == data.batch_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch number already exists",
        )

    if data.expiry_date <= data.manufacturing_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expiry_date must be after manufacturing_date",
        )

    batch = MedicineBatch(
        manufacturer_id=manufacturer.id,
        name=data.name,
        batch_number=data.batch_number,
        medicine_type=data.medicine_type,
        pack_size=data.pack_size,
        number_of_packs=data.number_of_packs,
        pieces_per_pack=data.pieces_per_pack,
        quantity=data.quantity,
        expiry_date=data.expiry_date,
        manufacturing_date=data.manufacturing_date,
        storage_temp_declared=data.storage_temp_declared,
    )
    db.add(batch)
    db.flush()

    signed_payload = {
        "action": "batch_creation",
        "batch_number": data.batch_number,
        "quantity": data.quantity,
        "manufacturer_id": manufacturer.id,
    }

    approval_log = _write_approval_log(
        db,
        current_user,
        action_type="batch_creation",
        entity_id=batch.id,
        entity_type="batch",
        notes=f"Batch {data.batch_number} created ({data.quantity} units)",
        signed_payload=signed_payload,
    )
    db.commit()
    db.refresh(batch)
    db.refresh(approval_log)

    return BatchResponse(
        id=batch.id,
        manufacturer_id=batch.manufacturer_id,
        name=batch.name,
        batch_number=batch.batch_number,
        quantity=batch.quantity,
        expiry_date=batch.expiry_date,
        manufacturing_date=batch.manufacturing_date,
        storage_temp_declared=batch.storage_temp_declared,
        approval_log_id=approval_log.id,
    )


@router.post("/shipments", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(
    data: ShipmentCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manufacturer),
):
    manufacturer = _get_manufacturer(db, current_user.entity_id)

    batch = (
        db.query(MedicineBatch)
        .filter(
            MedicineBatch.id == data.batch_id,
            MedicineBatch.manufacturer_id == manufacturer.id,
        )
        .first()
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or does not belong to your manufacturer",
        )

    supplier = db.query(Supplier).filter(Supplier.id == data.to_entity_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    partnership = db.query(TradePartnership).filter(
        TradePartnership.from_entity_id == manufacturer.id,
        TradePartnership.to_entity_id == supplier.id,
        TradePartnership.status == "active"
    ).first()
    if not partnership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispatch denied: No active trade partnership exists with this supplier."
        )

    remaining = remaining_units_for_batch(db, batch, manufacturer.id)
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

    shipment_code = f"SHP-{batch.batch_number}-{secrets.token_hex(3).upper()}"
    while db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first():
        shipment_code = f"SHP-{batch.batch_number}-{secrets.token_hex(3).upper()}"

    shipment = Shipment(
        batch_id=batch.id,
        from_entity_id=manufacturer.id,
        to_entity_id=supplier.id,
        shipment_code=shipment_code,
        quantity_dispatched=data.quantity,
        status="pending",
    )
    db.add(shipment)
    db.flush()

    verification_url = f"{settings.PUBLIC_APP_URL}/shared/shipment/{shipment.id}"
    qr_code_url = generate_shipment_qr(shipment.id, verification_url=verification_url)
    shipment.qr_code_url = qr_code_url

    signed_payload = {
        "action": "shipment_dispatch",
        "batch_id": batch.id,
        "shipment_code": shipment_code,
        "quantity_dispatched": data.quantity,
        "to_entity_id": supplier.id,
    }

    approval_log = _write_approval_log(
        db,
        current_user,
        action_type="shipment_dispatch",
        entity_id=shipment.id,
        entity_type="shipment",
        notes=(
            f"Dispatched {data.quantity} units of {batch.name} ({batch.batch_number}) "
            f"to {supplier.name} · code {shipment_code} · "
            f"{remaining - data.quantity} units remaining in batch"
        ),
        signed_payload=signed_payload,
    )
    db.commit()
    db.refresh(shipment)
    db.refresh(approval_log)

    background_tasks.add_task(
        bg_record_handoff_and_store,
        shipment.id,
        "dispatched",
        0.0,
        SessionLocal,
        Shipment,
        shipment.id,
        "blockchain_hash",
        approval_log.id,
    )

    return ShipmentResponse(
        id=shipment.id,
        batch_id=shipment.batch_id,
        from_entity_id=shipment.from_entity_id,
        to_entity_id=shipment.to_entity_id,
        shipment_code=shipment.shipment_code,
        quantity_dispatched=shipment.quantity_dispatched,
        qr_code_url=f"{settings.API_BASE_URL}{qr_code_url}",
        verification_url=verification_url,
        status=shipment.status,
        approval_log_id=approval_log.id,
    )


@router.get("/emergency-notifications", response_model=List[EmergencyNotificationItem])
def list_emergency_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manufacturer),
):
    manufacturer = _get_manufacturer(db, current_user.entity_id)
    requests = notifications_for_manufacturer(db, manufacturer.id)
    return to_notification_items(db, requests)


@router.get("/batches/{batch_id}/compliance-report")
def download_compliance_report(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manufacturer),
):
    """
    Stream a compliance PDF for the given batch.
    The PDF is generated on-demand from live DB data — nothing is stored on disk.
    """
    from reports.compliance_pdf import generate_compliance_pdf

    manufacturer = _get_manufacturer(db, current_user.entity_id)

    # Verify the batch belongs to this manufacturer
    batch = (
        db.query(MedicineBatch)
        .filter(
            MedicineBatch.id == batch_id,
            MedicineBatch.manufacturer_id == manufacturer.id,
        )
        .first()
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or does not belong to your manufacturer",
        )

    # Gather all ApprovalLog rows linked to this batch or any of its shipments
    from models import Shipment
    shipment_ids = [
        s.id for s in db.query(Shipment).filter(Shipment.batch_id == batch_id).all()
    ]
    entity_ids = [batch_id] + shipment_ids

    logs = (
        db.query(ApprovalLog)
        .filter(ApprovalLog.entity_id.in_(entity_ids))
        .order_by(ApprovalLog.created_at.asc())
        .all()
    )

    pdf_buf = generate_compliance_pdf(batch, manufacturer, logs)
    safe_name = (batch.batch_number or batch_id).replace("/", "-").replace(" ", "_")

    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="compliance-report-{safe_name}.pdf"'
        },
    )
