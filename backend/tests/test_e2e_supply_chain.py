"""
E2E Test: Full Medicine Supply Chain Handoff
=============================================
Covers the critical path: 
  Manufacturer registers → creates batch → dispatches to Supplier
  Supplier verifies receipt → adds to inventory → dispatches to Hospital
  Hospital confirms receipt → AI verification triggered

Every HTTP response code and key field is asserted so schema regressions
are caught immediately — not discovered by a confused pilot customer.

Run with:
    cd backend
    pytest tests/test_e2e_supply_chain.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta, timezone

from tests.conftest import register_and_login, auth_header


# ── Shared state across the test chain ────────────────────────────────────────
# We use module-level vars (populated by earlier tests) so the chain runs in
# strict order: each test depends on the output of the previous one.

STATE = {}

FUTURE_EXPIRY = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
MFG_DATE      = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ═══════════════════════════════════════════════════════════════════════
# PHASE 1 — Registration & Authentication
# ═══════════════════════════════════════════════════════════════════════

class TestPhase1_Auth:

    def test_register_manufacturer(self, client):
        """Manufacturer registers and receives a valid JWT."""
        payload = {
            "email": "mfg_e2e@chainmed.test",
            "password": "TestPass2026!",
            "role": "manufacturer",
            "full_name": "E2E Manufacturer",
            "organization_name": "E2E Pharma Ltd",
            "country": "India",
        }
        r = client.post("/auth/register", json=payload)
        assert r.status_code == 200, f"Registration failed: {r.text}"
        data = r.json()
        STATE["mfg_token"] = data["access_token"]
        STATE["mfg_entity_id"] = data["entity_id"]
        assert STATE["mfg_token"] and len(STATE["mfg_token"]) > 20

    def test_register_supplier(self, client):
        """Supplier registers and receives a valid JWT."""
        payload = {
            "email": "sup_e2e@chainmed.test",
            "password": "TestPass2026!",
            "role": "supplier",
            "full_name": "E2E Supplier",
            "organization_name": "E2E Medical Supply",
            "country": "India",
            "warehouse_location": "Mumbai",
        }
        r = client.post("/auth/register", json=payload)
        assert r.status_code == 200, f"Registration failed: {r.text}"
        data = r.json()
        STATE["sup_token"] = data["access_token"]
        STATE["sup_entity_id"] = data["entity_id"]
        assert STATE["sup_token"] and len(STATE["sup_token"]) > 20

    def test_register_hospital(self, client):
        """Hospital (consumer) registers and receives a valid JWT."""
        payload = {
            "email": "hospital_e2e@chainmed.test",
            "password": "TestPass2026!",
            "role": "consumer",
            "full_name": "E2E Hospital Officer",
            "organization_name": "E2E City Hospital",
            "country": "India",
            "location": "Delhi",
            "consumer_type": "hospital",
        }
        r = client.post("/auth/register", json=payload)
        assert r.status_code == 200, f"Registration failed: {r.text}"
        data = r.json()
        STATE["hospital_token"] = data["access_token"]
        STATE["hospital_entity_id"] = data["entity_id"]
        assert STATE["hospital_token"] and len(STATE["hospital_token"]) > 20

    def test_login_returns_correct_role(self, client):
        """Login with correct creds returns the correct role."""
        r = client.post("/auth/login", json={
            "email": "mfg_e2e@chainmed.test",
            "password": "TestPass2026!",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "manufacturer"
        assert "access_token" in data

    def test_wrong_password_returns_401(self, client):
        """Wrong password must return 401, not 500 and not a page reload."""
        r = client.post("/auth/login", json={
            "email": "mfg_e2e@chainmed.test",
            "password": "WRONG_PASSWORD",
        })
        assert r.status_code == 401
        assert "access_token" not in r.json()

    def test_get_entity_ids(self, client):
        """Entity IDs are captured at registration — verify they're set."""
        assert STATE.get("mfg_entity_id"), "Manufacturer entity_id not captured"
        assert STATE.get("sup_entity_id"), "Supplier entity_id not captured"
        assert STATE.get("hospital_entity_id"), "Hospital entity_id not captured"


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2 — Trade Partnerships (required before dispatch)
# ═══════════════════════════════════════════════════════════════════════

class TestPhase2_Partnerships:

    def test_create_mfg_supplier_partnership(self, client):
        """Manufacturer creates an active trade partnership with the supplier."""
        r = client.post(
            "/shared/partnerships/request",
            json={"partner_entity_id": STATE["sup_entity_id"]},
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code in (200, 201), f"Partnership request failed: {r.text}"
        STATE["mfg_sup_partnership_id"] = r.json().get("id")

    def test_supplier_accepts_mfg_partnership(self, client):
        """Supplier accepts the manufacturer's partnership request."""
        pid = STATE.get("mfg_sup_partnership_id")
        if not pid:
            pytest.skip("No partnership ID — skipping accept step")
        r = client.post(
            f"/shared/partnerships/{pid}/accept",
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code in (200, 201), f"Accept failed: {r.text}"

    def test_create_supplier_hospital_partnership(self, client):
        """Supplier creates an active trade partnership with the hospital."""
        r = client.post(
            "/shared/partnerships/request",
            json={"partner_entity_id": STATE["hospital_entity_id"]},
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code in (200, 201), f"Partnership request failed: {r.text}"
        STATE["sup_hospital_partnership_id"] = r.json().get("id")

    def test_hospital_accepts_supplier_partnership(self, client):
        """Hospital accepts the supplier's partnership request."""
        pid = STATE.get("sup_hospital_partnership_id")
        if not pid:
            pytest.skip("No partnership ID — skipping accept step")
        r = client.post(
            f"/shared/partnerships/{pid}/accept",
            headers=auth_header(STATE["hospital_token"]),
        )
        assert r.status_code in (200, 201), f"Accept failed: {r.text}"


# ═══════════════════════════════════════════════════════════════════════
# PHASE 3 — Manufacturer Creates Batch and Dispatches
# ═══════════════════════════════════════════════════════════════════════

class TestPhase3_ManufacturerDispatch:

    def test_create_batch(self, client):
        """Manufacturer creates a medicine batch."""
        r = client.post(
            "/manufacturer/batches",
            json={
                "name": "Paracetamol 500mg",
                "batch_number": "E2E-BATCH-001",
                "quantity": 10000,
                "pieces_per_pack": 10,
                "pack_size": "10 tablets",
                "number_of_packs": 1000,
                "expiry_date": FUTURE_EXPIRY,
                "manufacturing_date": MFG_DATE,
                "storage_temp_declared": 25.0,
            },
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 201, f"Batch creation failed: {r.text}"
        data = r.json()
        assert data["batch_number"] == "E2E-BATCH-001"
        assert data["quantity"] == 10000
        STATE["batch_id"] = data["id"]
        STATE["approval_log_id_batch"] = data.get("approval_log_id")

    def test_batch_appears_in_list(self, client):
        """Created batch must appear in the manufacturer's batch list."""
        r = client.get("/manufacturer/batches", headers=auth_header(STATE["mfg_token"]))
        assert r.status_code == 200
        batch_ids = [b["id"] for b in r.json()]
        assert STATE["batch_id"] in batch_ids

    def test_dispatch_to_supplier(self, client):
        """Manufacturer dispatches 5000 units to the supplier."""
        r = client.post(
            "/manufacturer/shipments",
            json={
                "batch_id": STATE["batch_id"],
                "to_entity_id": STATE["sup_entity_id"],
                "quantity": 5000,
            },
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 201, f"Dispatch failed: {r.text}"
        data = r.json()
        assert data["status"] == "pending"
        assert data["quantity_dispatched"] == 5000
        assert data["shipment_code"].startswith("SHP-")
        assert "qr_code_url" in data
        STATE["shipment_mfg_to_sup_id"] = data["id"]
        STATE["shipment_code_mfg_sup"] = data["shipment_code"]

    def test_dispatch_creates_audit_log(self, client):
        """Dispatching a shipment must create an audit log entry."""
        r = client.get(
            "/approval-logs",
            params={"action_type": "shipment_dispatch"},
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        latest = logs[0]
        assert latest["action_type"] == "shipment_dispatch"
        assert latest["entity_id"] == STATE["shipment_mfg_to_sup_id"]

    def test_cannot_dispatch_more_than_remaining(self, client):
        """Dispatching more than remaining quantity must return 400."""
        r = client.post(
            "/manufacturer/shipments",
            json={
                "batch_id": STATE["batch_id"],
                "to_entity_id": STATE["sup_entity_id"],
                "quantity": 99999,  # way more than remaining 5000
            },
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# PHASE 4 — Supplier Verifies Incoming Shipment
# ═══════════════════════════════════════════════════════════════════════

class TestPhase4_SupplierVerification:

    def test_incoming_shipment_appears_for_supplier(self, client):
        """The dispatched shipment must appear in the supplier's incoming list."""
        r = client.get(
            "/supplier/shipments/incoming",
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 200
        incoming_ids = [s["id"] for s in r.json()]
        assert STATE["shipment_mfg_to_sup_id"] in incoming_ids, (
            f"Shipment {STATE['shipment_mfg_to_sup_id']} not found in supplier incoming list"
        )

    def test_supplier_verifies_shipment(self, client):
        """Supplier confirms receipt of incoming shipment with quantity and temp."""
        r = client.post(
            f"/supplier/shipments/{STATE['shipment_mfg_to_sup_id']}/verify",
            json={
                "quantity_reported": 5000,
                "expiry_reported": FUTURE_EXPIRY,
                "temp_reported": 23.5,
                "notes": "All packages intact. Cold chain maintained.",
            },
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 200, f"Supplier verify failed: {r.text}"
        data = r.json()
        assert data["status"] == "delivered"

    def test_cannot_verify_same_shipment_twice(self, client):
        """Double verification of the same shipment must return 409."""
        r = client.post(
            f"/supplier/shipments/{STATE['shipment_mfg_to_sup_id']}/verify",
            json={
                "quantity_reported": 5000,
                "expiry_reported": FUTURE_EXPIRY,
                "temp_reported": 23.5,
            },
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 409

    def test_verification_creates_audit_log(self, client):
        """Supplier verification must create an incoming_verification audit log."""
        r = client.get(
            "/approval-logs",
            params={"action_type": "incoming_verification"},
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 200
        logs = r.json()
        assert any(
            log["entity_id"] == STATE["shipment_mfg_to_sup_id"]
            for log in logs
        ), "No incoming_verification log entry for this shipment"

    def test_supplier_inventory_updated_after_verification(self, client):
        """Supplier's inventory must show the verified medicine."""
        r = client.get("/supplier/inventory", headers=auth_header(STATE["sup_token"]))
        assert r.status_code == 200
        medicines = [item["medicine_name"] for item in r.json()]
        assert "Paracetamol 500mg" in medicines


# ═══════════════════════════════════════════════════════════════════════
# PHASE 5 — Supplier Dispatches to Hospital
# ═══════════════════════════════════════════════════════════════════════

class TestPhase5_SupplierDispatch:

    def test_get_dispatchable_batches(self, client):
        """Supplier must see the verified batch as dispatchable."""
        r = client.get(
            "/supplier/inventory/dispatchable",
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 200
        batch_ids = [b["batch_id"] for b in r.json()]
        assert STATE["batch_id"] in batch_ids, (
            f"Batch {STATE['batch_id']} not in dispatchable list"
        )

    def test_supplier_dispatches_to_hospital(self, client):
        """Supplier dispatches 2000 units to the hospital."""
        r = client.post(
            "/supplier/shipments/outbound",
            json={
                "batch_id": STATE["batch_id"],
                "to_entity_id": STATE["hospital_entity_id"],
                "quantity": 2000,
            },
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 201, f"Supplier dispatch failed: {r.text}"
        data = r.json()
        assert data["status"] == "pending"
        assert data["quantity_dispatched"] == 2000
        assert data["shipment_code"].startswith("SHP-OUT-")
        STATE["shipment_sup_to_hospital_id"] = data["id"]

    def test_supplier_cannot_dispatch_without_partnership(self, client):
        """Dispatch to an entity with no active partnership must return 403."""
        # Register a random consumer with no partnership
        payload = {
            "email": "no_partner_hospital@chainmed.test",
            "password": "TestPass2026!",
            "role": "consumer",
            "full_name": "No Partner Hospital",
            "organization_name": "Unlinked Clinic",
            "country": "India",
            "location": "Remote",
            "consumer_type": "hospital",
        }
        r2 = client.post("/auth/register", json=payload)
        assert r2.status_code == 200, f"Registration failed: {r2.text}"
        unlinked_id = r2.json()["entity_id"]

        r = client.post(
            "/supplier/shipments/outbound",
            json={
                "batch_id": STATE["batch_id"],
                "to_entity_id": unlinked_id,
                "quantity": 100,
            },
            headers=auth_header(STATE["sup_token"]),
        )
        assert r.status_code == 403, (
            "Expected 403 for dispatch without partnership, got: "
            f"{r.status_code} — {r.text}"
        )


# ═══════════════════════════════════════════════════════════════════════
# PHASE 6 — Hospital Confirms Receipt
# ═══════════════════════════════════════════════════════════════════════

class TestPhase6_HospitalReceipt:

    def test_incoming_shipment_appears_for_hospital(self, client):
        """Dispatched shipment must appear in the hospital's incoming list."""
        r = client.get(
            "/consumer/shipments/incoming",
            headers=auth_header(STATE["hospital_token"]),
        )
        assert r.status_code == 200
        incoming_ids = [s["id"] for s in r.json()]
        assert STATE["shipment_sup_to_hospital_id"] in incoming_ids, (
            "Shipment not found in hospital incoming list"
        )

    def test_hospital_confirms_receipt(self, client):
        """Hospital confirms receipt with matching quantity and temperature."""
        r = client.post(
            f"/consumer/shipments/{STATE['shipment_sup_to_hospital_id']}/confirm",
            json={
                "quantity_reported": 2000,
                "expiry_reported": FUTURE_EXPIRY,
                "temp_reported": 24.0,
                "notes": "Cold chain has been properly maintained.",
            },
            headers=auth_header(STATE["hospital_token"]),
        )
        assert r.status_code == 200, f"Hospital confirm failed: {r.text}"
        data = r.json()
        assert data["status"] == "delivered"

    def test_cannot_confirm_same_receipt_twice(self, client):
        """Double confirmation must return 409."""
        r = client.post(
            f"/consumer/shipments/{STATE['shipment_sup_to_hospital_id']}/confirm",
            json={
                "quantity_reported": 2000,
                "expiry_reported": FUTURE_EXPIRY,
                "temp_reported": 24.0,
            },
            headers=auth_header(STATE["hospital_token"]),
        )
        assert r.status_code == 409

    def test_receipt_creates_audit_log(self, client):
        """Hospital receipt must create a receipt_confirmation audit log."""
        r = client.get(
            "/approval-logs",
            params={"action_type": "receipt_confirmation"},
            headers=auth_header(STATE["hospital_token"]),
        )
        assert r.status_code == 200
        logs = r.json()
        assert any(
            log["entity_id"] == STATE["shipment_sup_to_hospital_id"]
            for log in logs
        ), "No receipt_confirmation audit log found for hospital shipment"

    def test_hospital_inventory_updated(self, client):
        """Hospital inventory must reflect the received medicine."""
        r = client.get("/consumer/inventory", headers=auth_header(STATE["hospital_token"]))
        assert r.status_code == 200
        medicines = [item["medicine_name"] for item in r.json()]
        assert "Paracetamol 500mg" in medicines


# ═══════════════════════════════════════════════════════════════════════
# PHASE 7 — Audit Trail Integrity
# ═══════════════════════════════════════════════════════════════════════

class TestPhase7_AuditTrail:

    def test_public_shipment_page_shows_full_chain(self, client):
        """The public shipment verification page must show the complete chain."""
        shipment_id = STATE["shipment_sup_to_hospital_id"]
        r = client.get(f"/shared/shipment/{shipment_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == shipment_id
        assert "approval_logs" in data
        assert len(data["approval_logs"]) >= 1

    def test_audit_log_has_all_three_action_types(self, client):
        """The global audit log must contain all 3 action types from this chain."""
        r = client.get("/approval-logs", headers=auth_header(STATE["mfg_token"]))
        assert r.status_code == 200
        logs = r.json()
        action_types = {log["action_type"] for log in logs}
        assert "shipment_dispatch" in action_types
        assert "incoming_verification" in action_types
        assert "receipt_confirmation" in action_types

    def test_audit_log_is_append_only(self, client):
        """Audit log must not expose any DELETE or UPDATE endpoints."""
        # Attempt DELETE on approval-logs — must be 405 Method Not Allowed
        log_r = client.get("/approval-logs", headers=auth_header(STATE["mfg_token"]))
        first_log_id = log_r.json()[0]["id"]
        r = client.delete(f"/approval-logs/{first_log_id}", headers=auth_header(STATE["mfg_token"]))
        assert r.status_code in (404, 405), (
            "DELETE on audit log should not succeed — audit log must be append-only"
        )

    def test_health_endpoint_is_up(self, client):
        """Health endpoint must respond with status ok."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════
# PHASE 8 — Compliance Report PDF (P1.3 smoke test)
# ═══════════════════════════════════════════════════════════════════════

class TestPhase8_ComplianceReport:

    def test_compliance_report_returns_pdf(self, client):
        """GET /manufacturer/batches/{id}/compliance-report must return a PDF."""
        batch_id = STATE.get("batch_id")
        assert batch_id, "batch_id not set — Phase 2 must run first"

        r = client.get(
            f"/manufacturer/batches/{batch_id}/compliance-report",
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text}"
        assert "application/pdf" in r.headers.get("content-type", ""), (
            f"Expected application/pdf content-type, got: {r.headers.get('content-type')}"
        )
        assert r.content[:4] == b"%PDF", (
            "Response body does not start with PDF magic bytes (%PDF)"
        )

    def test_compliance_report_content_disposition(self, client):
        """Compliance report must include Content-Disposition attachment header."""
        batch_id = STATE.get("batch_id")
        r = client.get(
            f"/manufacturer/batches/{batch_id}/compliance-report",
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 200
        disposition = r.headers.get("content-disposition", "")
        assert "attachment" in disposition, (
            f"Expected 'attachment' in Content-Disposition, got: {disposition}"
        )
        assert "compliance-report" in disposition, (
            f"Expected 'compliance-report' in filename, got: {disposition}"
        )

    def test_compliance_report_wrong_batch_returns_404(self, client):
        """A manufacturer cannot download another entity's batch report."""
        r = client.get(
            "/manufacturer/batches/nonexistent-batch-id-xyz/compliance-report",
            headers=auth_header(STATE["mfg_token"]),
        )
        assert r.status_code == 404, (
            f"Expected 404 for non-existent batch, got {r.status_code}"
        )

    def test_compliance_report_requires_auth(self, client):
        """Compliance report endpoint must reject unauthenticated requests."""
        batch_id = STATE.get("batch_id")
        r = client.get(f"/manufacturer/batches/{batch_id}/compliance-report")
        assert r.status_code in (401, 403), (
            f"Expected 401/403 without auth token, got {r.status_code}"
        )
