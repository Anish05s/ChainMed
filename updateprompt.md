# ChainMed_UpdatePrompt.md
# ADDITIONS ONLY — Nothing in this file exists in ChainMed_MasterPrompt_Classic.md
# Use this with Cursor, Antigravity, Claude, or any AI to update the existing GitHub repo.
# Context: Project is live at ChainMed-mauve.vercel.app, backend on Railway, repo at github.com/Anish05s/ChainMed

---

## INSTRUCTION FOR AI

You are updating an existing project. Do NOT regenerate files that already work.
Only implement the additions listed below. Each section is a standalone task.
Read existing files before editing. Preserve all existing logic.

---

## ADDITION 1 — ECDSA MULTI-SIGNATURE VALIDATION LAYER

**Why:** Current system only hashes data with SHA-256. No cryptographic proof that the submitting party actually signed it. Any backend process could forge a handoff record.

**What to build:** `backend/auth/signing.py`

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import base64, json

def generate_entity_keypair() -> dict:
    """Generate secp256k1 keypair for an entity on registration."""
    private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
    public_key = private_key.public_key()
    return {
        "private_key_pem": private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).decode(),
        "public_key_pem": public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
    }

def sign_handoff(private_key_pem: str, handoff_data: dict) -> str:
    """Entity signs their handoff submission. Returns base64 signature."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None, backend=default_backend()
    )
    payload = json.dumps(handoff_data, sort_keys=True).encode()
    signature = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode()

def verify_handoff_signature(public_key_pem: str, handoff_data: dict, signature_b64: str) -> bool:
    """Verify a party's signature on their handoff data. Returns True if valid."""
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), backend=default_backend()
        )
        payload = json.dumps(handoff_data, sort_keys=True).encode()
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
```

**Schema changes:**
- Add `public_key_pem TEXT` column to `manufacturers`, `suppliers`, `consumers` tables
- Add `private_key_pem TEXT` column to same tables (encrypted at rest in production)
- Add `signature VARCHAR(512)` column to `handoff_records` table
- Add `signature_verified BOOLEAN DEFAULT false` column to `handoff_records`

**Integration:**
- In `auth/router.py` register endpoint: call `generate_entity_keypair()` and store both keys on the entity row
- In each party's verify/confirm endpoint: receive `signature` field in request body, call `verify_handoff_signature()` before creating HandoffRecord, store result in `signature_verified`
- In `verification_ai/engine.py`: if any handoff has `signature_verified = false`, add +20 to risk_score with rule name `unverified_signature`

**Install:**
```bash
pip install cryptography
```

---

## ADDITION 2 — PERFORMANCE BENCHMARKING MODULE

**Why:** No paper can be published without empirical evaluation. No investor will trust unverified claims.

**What to build:** `backend/benchmarks/runner.py`

```python
"""
Run this script to generate performance metrics for the research paper.
Usage: python -m benchmarks.runner
Outputs: benchmarks/results.json
"""
import time, statistics, json, asyncio
from uuid import uuid4

METRICS = {}

def benchmark_verification_ai(n=1000):
    """Measure Verification AI latency over n iterations."""
    from verification_ai.engine import run_verification_sync
    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        run_verification_sync(mock=True)
        latencies.append((time.perf_counter() - start) * 1000)  # ms
    METRICS["verification_ai"] = {
        "mean_ms": statistics.mean(latencies),
        "p95_ms": sorted(latencies)[int(0.95 * n)],
        "p99_ms": sorted(latencies)[int(0.99 * n)],
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "n": n
    }

def benchmark_false_positive_rate(n=500):
    """
    Send clean three-party data (no mismatches) through rule engine.
    Count how many are incorrectly FLAGGED.
    False Positive Rate = FLAGGED_count / n
    """
    from verification_ai.engine import compute_risk_score
    false_positives = 0
    for _ in range(n):
        # All three parties report identical clean data
        result = compute_risk_score(
            quantities=[1000, 1000, 1000],
            expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
            batch_numbers=["BATCH001", "BATCH001", "BATCH001"],
            medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
            temps=[22.0, 23.0, 22.5],
        )
        if result["status"] == "FLAGGED":
            false_positives += 1
    METRICS["false_positive_rate"] = {
        "rate": false_positives / n,
        "count": false_positives,
        "n": n
    }

def benchmark_blockchain_latency(n=20):
    """Measure mock blockchain write latency."""
    from blockchain_service import get_blockchain_service
    svc = get_blockchain_service()
    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        svc.record_handoff(str(uuid4()), "abc123", "VERIFIED", 10)
        latencies.append((time.perf_counter() - start) * 1000)
    METRICS["blockchain_mock_write"] = {
        "mean_ms": statistics.mean(latencies),
        "n": n
    }

if __name__ == "__main__":
    benchmark_verification_ai()
    benchmark_false_positive_rate()
    benchmark_blockchain_latency()
    with open("benchmarks/results.json", "w") as f:
        json.dump(METRICS, f, indent=2)
    print(json.dumps(METRICS, indent=2))
```

Also add `benchmarks/__init__.py` (empty) and `benchmarks/results.json` (gitignored).

---

## ADDITION 3 — RATE LIMITING ON ALL AUTH ENDPOINTS

**Why:** Current auth has no brute force protection. Critical security gap for production.

**What to add in `main.py`:**

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**In `auth/router.py` login endpoint:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

**In `auth/router.py` register endpoint:**
```python
@router.post("/auth/register")
@limiter.limit("3/minute")
async def register(request: Request, ...):
    ...
```

**Install:**
```bash
pip install slowapi
```

---

## ADDITION 4 — JWT LOGOUT WITH REDIS TOKEN BLACKLIST

**Why:** Current 24-hour JWT has no invalidation mechanism. If a hospital officer is terminated, their token stays valid.

**Add to `auth/router.py`:**

```python
import redis as redis_client
from auth.utils import decode_token

r = redis_client.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/auth/logout")
def logout(
    current_user=Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    """Blacklist the current JWT until it expires."""
    payload = decode_token(token)
    exp = payload.get("exp", 0)
    ttl = max(int(exp - time.time()), 1)
    r.setex(f"blacklist:{token}", ttl, "1")
    return {"message": "Logged out successfully"}
```

**Update `auth/dependencies.py` `get_current_user`:**
```python
# After decoding token, before returning user:
if r.exists(f"blacklist:{token}"):
    raise HTTPException(status_code=401, detail="Token has been invalidated")
```

**Update token expiry in `auth/utils.py`:**
```python
# Change from 24 hours to 15 minutes for access tokens
ACCESS_TOKEN_EXPIRE_MINUTES = 15
```

---

## ADDITION 5 — CORS PRODUCTION GUARD

**Why:** `ALLOWED_ORIGINS=*` will be deployed to production accidentally and is a security risk.

**Add to `main.py` lifespan startup:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # PRODUCTION SAFETY GUARD
    if settings.ENVIRONMENT == "production" and settings.ALLOWED_ORIGINS == "*":
        raise RuntimeError(
            "CRITICAL: ALLOWED_ORIGINS must not be '*' in production. "
            "Set it to your exact frontend domain."
        )
    # ... rest of startup
    yield
```

---

## ADDITION 6 — PYTEST TEST SUITE (MINIMUM VIABLE)

**Why:** Zero tests currently. Even 5 tests dramatically increases credibility for research paper and investor demo.

**Create `backend/tests/test_verification_ai.py`:**

```python
import pytest
from verification_ai.engine import compute_risk_score

def test_clean_shipment_is_verified():
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 23.0, 22.5],
    )
    assert result["status"] == "VERIFIED"
    assert result["risk_score"] < 30

def test_quantity_deviation_flags():
    result = compute_risk_score(
        quantities=[10000, 8200, 8200],  # 18% deviation
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Amoxicillin", "Amoxicillin", "Amoxicillin"],
        temps=[22.0, 22.0, 22.0],
    )
    assert result["status"] == "FLAGGED"
    assert result["risk_score"] >= 50
    assert "quantity_deviation_gt_15pct" in result["triggered_rules"]

def test_expiry_mismatch_raises_risk():
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2026-06-01", "2027-01-01"],  # mismatch
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 22.0, 22.0],
    )
    assert result["risk_score"] >= 25
    assert "expiry_date_mismatch" in result["triggered_rules"]

def test_temperature_breach_adds_risk():
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 35.0, 22.0],  # breach
    )
    assert "temperature_breach" in result["triggered_rules"]

def test_risk_score_never_exceeds_100():
    result = compute_risk_score(
        quantities=[10000, 5000, 5000],  # 50% deviation
        expiries=["2027-01-01", "2026-01-01", "2025-01-01"],  # mismatch
        batch_numbers=["B001", "B002", "B003"],  # mismatch
        medicine_names=["DrugA", "DrugB", "DrugC"],  # mismatch
        temps=[22.0, 38.0, 22.0],  # breach
    )
    assert result["risk_score"] <= 100

def test_pending_when_less_than_two_parties():
    # Only 1 handoff — can't cross-match yet
    result = compute_risk_score(
        quantities=[1000],
        expiries=["2027-01-01"],
        batch_numbers=["B001"],
        medicine_names=["Paracetamol"],
        temps=[22.0],
    )
    assert result["status"] == "PENDING"
```

**Create `backend/tests/__init__.py`** (empty)

**Run with:**
```bash
cd backend
pytest tests/ -v
```

**Install:**
```bash
pip install pytest pytest-asyncio
```

---

## ADDITION 7 — DISRUPTION EVENTS TABLE + MIGRATION

**Why:** The `crisis_ai` module exists in code but the `disruption_events` DB table was never added to the Alembic migrations.

**Create new migration `backend/alembic/versions/003_add_disruption_events.py`:**

```python
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'

def upgrade():
    op.create_table(
        'disruption_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('event_type', sa.String()),
        sa.Column('region', sa.String()),
        sa.Column('severity', sa.String()),
        sa.Column('description', sa.Text()),
        sa.Column('affected_routes', sa.JSON()),
        sa.Column('recommended_medicines', sa.JSON()),
        sa.Column('source', sa.String()),
        sa.Column('resolved', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('disruption_events')
```

**Add ORM model to `models.py`:**
```python
class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    id = Column(String, primary_key=True)
    event_type = Column(String)
    region = Column(String)
    severity = Column(String)
    description = Column(Text)
    affected_routes = Column(JSON)
    recommended_medicines = Column(JSON)
    source = Column(String, default="manual")
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## ADDITION 8 — ADMIN PORTAL BACKEND

**Why:** No admin override capability exists. Compliance requires ability to manually override AI flags with justification.

**Create `backend/admin/router.py`:**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4
from database import get_db
from models import AIFlag, ApprovalLog, User, Manufacturer, Supplier, Consumer
from auth.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/trust-scores")
def list_all_trust_scores(
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    """List trust scores across all entity types."""
    mfrs = db.query(Manufacturer.id, Manufacturer.name, Manufacturer.trust_score).all()
    sups = db.query(Supplier.id, Supplier.name, Supplier.trust_score).all()
    cons = db.query(Consumer.id, Consumer.name, Consumer.trust_score).all()
    return {
        "manufacturers": [{"id": r.id, "name": r.name, "trust_score": r.trust_score} for r in mfrs],
        "suppliers": [{"id": r.id, "name": r.name, "trust_score": r.trust_score} for r in sups],
        "consumers": [{"id": r.id, "name": r.name, "trust_score": r.trust_score} for r in cons],
    }

@router.post("/flags/{flag_id}/override")
def override_flag(
    flag_id: str,
    justification: str,
    new_status: str,  # VERIFIED or CLEARED
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin manually overrides an AI flag with written justification."""
    flag = db.query(AIFlag).filter(AIFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    old_status = flag.status
    flag.status = new_status

    log = ApprovalLog(
        id=str(uuid4()),
        actor_role="admin",
        actor_name=current_user.full_name or current_user.email,
        actor_id=current_user.id,
        action_type="ai_flag_override",
        entity_id=flag_id,
        entity_type="ai_flag",
        notes=f"Flag overridden from {old_status} to {new_status}. Justification: {justification}",
        metadata={"old_status": old_status, "new_status": new_status, "justification": justification}
    )
    db.add(log)
    db.commit()
    return {"flag_id": flag_id, "new_status": new_status, "approval_log_id": log.id}

@router.get("/approval-logs/all")
def list_all_approval_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    """Admin-only: view approval logs across ALL entities."""
    return db.query(ApprovalLog).order_by(ApprovalLog.created_at.desc()).limit(limit).all()
```

**Add to `auth/dependencies.py`:**
```python
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

**Add `admin` role to user registration flow and `users` table.**

**Mount in `main.py`:**
```python
from admin.router import router as admin_router
app.include_router(admin_router)
```

---

## ADDITION 9 — SEEDER SCRIPT FOR DEMO

**Why:** No demo data script exists. Essential for hackathon demo and testing.

**Create `backend/seed.py`:**

```python
"""
Seed ChainMed with demo data for testing and hackathon demos.
Run: python seed.py
Creates 3 demo accounts (one per role) + a sample shipment pipeline.
"""
import httpx, json

BASE = "http://localhost:8000"

def register(email, password, role, org, full_name):
    r = httpx.post(f"{BASE}/auth/register", json={
        "email": email, "password": password,
        "role": role, "organization_name": org, "full_name": full_name
    })
    return r.json()

def login(email, password):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]

if __name__ == "__main__":
    print("Registering demo accounts...")
    register("mfr@demo.com", "Demo@1234", "manufacturer", "Apollo Pharmaceuticals", "Ravi Kumar")
    register("sup@demo.com", "Demo@1234", "supplier", "NorthEast Medical Supply", "Priya Sharma")
    register("hos@demo.com", "Demo@1234", "consumer", "Civil Hospital Guwahati", "Dr. Anand Mehta")

    mfr_token = login("mfr@demo.com", "Demo@1234")
    sup_token = login("sup@demo.com", "Demo@1234")
    hos_token = login("hos@demo.com", "Demo@1234")

    headers_mfr = {"Authorization": f"Bearer {mfr_token}"}
    headers_sup = {"Authorization": f"Bearer {sup_token}"}
    headers_hos = {"Authorization": f"Bearer {hos_token}"}

    # Create batch
    batch = httpx.post(f"{BASE}/manufacturer/batches", headers=headers_mfr, json={
        "batch_number": "AMX-2026-001",
        "name": "Amoxicillin 500mg",
        "quantity": 10000,
        "manufacturing_date": "2026-01-01",
        "expiry_date": "2028-01-01"
    }).json()
    print(f"Batch created: {batch['id']}")

    # Create + dispatch shipment
    sup_id = login("sup@demo.com", "Demo@1234")
    # (get supplier entity_id from token or profile endpoint)
    print("Demo seed complete. Login at /login with mfr@demo.com / Demo@1234")
```

---

## ADDITION 10 — RESEARCH PAPER MATH IN CODE (RISK FORMULA REFACTOR)

**Why:** The research paper uses a formal formula. The code must match exactly for reproducibility claims.

**Refactor `verification_ai/engine.py` to expose `compute_risk_score()` as a standalone pure function (no DB calls) so it can be unit-tested and benchmarked independently:**

```python
def compute_risk_score(
    quantities: list[int],
    expiries: list[str],
    batch_numbers: list[str],
    medicine_names: list[str],
    temps: list[float],
) -> dict:
    """
    Pure function. No DB access. Matches the research paper formula exactly.

    R = min(sum(w_i * f_i), 100)

    Weights:
      f1 (qty_dev > 15%): w=40
      f2 (qty_dev > 30%, additive): w=20
      f3 (expiry mismatch): w=25
      f4 (batch_num mismatch): w=30
      f5 (medicine_name mismatch): w=30
      f6 (temp > 30C): w=15
    """
    if len(quantities) < 2:
        return {"status": "PENDING", "risk_score": 0.0, "triggered_rules": [], "mismatch_fields": {}}

    risk = 0.0
    triggered_rules = []
    mismatch_fields = {}

    # f1, f2 — Quantity deviation
    q_max, q_min = max(quantities), min(quantities)
    delta_q = ((q_max - q_min) / q_min * 100) if q_min > 0 else 0
    if delta_q > 15:
        risk += 40
        triggered_rules.append("quantity_deviation_gt_15pct")
        mismatch_fields["quantity"] = {"values": quantities, "deviation_pct": round(delta_q, 2)}
    if delta_q > 30:
        risk += 20
        triggered_rules.append("quantity_deviation_gt_30pct")

    # f3 — Expiry mismatch
    if len(set(expiries)) > 1:
        risk += 25
        triggered_rules.append("expiry_date_mismatch")
        mismatch_fields["expiry"] = {"values": list(set(expiries))}

    # f4 — Batch number mismatch
    if len(set(batch_numbers)) > 1:
        risk += 30
        triggered_rules.append("batch_number_mismatch")
        mismatch_fields["batch_number"] = {"values": list(set(batch_numbers))}

    # f5 — Medicine name mismatch
    if len(set(medicine_names)) > 1:
        risk += 30
        triggered_rules.append("medicine_name_mismatch")
        mismatch_fields["medicine_name"] = {"values": list(set(medicine_names))}

    # f6 — Temperature breach
    if any(t > 30 for t in temps):
        risk += 15
        triggered_rules.append("temperature_breach")
        mismatch_fields["temperature"] = {"max_reported": max(temps)}

    risk = min(risk, 100.0)

    if risk < 30:
        status = "VERIFIED"
    elif risk >= 50:
        status = "FLAGGED"
    else:
        status = "PENDING"

    return {
        "status": status,
        "risk_score": risk,
        "triggered_rules": triggered_rules,
        "mismatch_fields": mismatch_fields,
    }
```

**The existing `run_verification(shipment_id, db)` function should call `compute_risk_score()` internally, passing values loaded from DB.**

---

## ADDITION 11 — FRONTEND: ADMIN DASHBOARD PAGE

**Create `frontend/src/pages/AdminDashboard.jsx`:**

```jsx
import React, { useState, useEffect } from 'react';
import API from '../api/auth';

export default function AdminDashboard() {
  const [trustScores, setTrustScores] = useState(null);
  const [flags, setFlags] = useState([]);
  const [justification, setJustification] = useState('');

  useEffect(() => {
    API.get('/admin/trust-scores').then(r => setTrustScores(r.data));
    API.get('/verification-ai/flags/risk/50').then(r => setFlags(r.data));
  }, []);

  const overrideFlag = async (flagId) => {
    if (!justification.trim()) return alert('Justification required');
    await API.post(`/admin/flags/${flagId}/override`, null, {
      params: { justification, new_status: 'VERIFIED' }
    });
    setFlags(flags.filter(f => f.id !== flagId));
  };

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold text-green-400">Admin Portal</h1>

      {/* Trust Scores */}
      {trustScores && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Entity Trust Scores</h2>
          <div className="grid grid-cols-3 gap-4">
            {['manufacturers','suppliers','consumers'].map(type =>
              trustScores[type]?.map(e => (
                <div key={e.id} className="bg-gray-800 p-3 rounded border border-gray-700">
                  <p className="font-medium">{e.name}</p>
                  <p className={`text-xl font-bold ${e.trust_score > 80 ? 'text-green-400' : e.trust_score > 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {e.trust_score.toFixed(1)}/100
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Active Flags */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Active High-Risk Flags (≥50)</h2>
        <input
          className="mb-3 w-full p-2 bg-gray-800 border border-gray-600 rounded text-white"
          placeholder="Justification for override..."
          value={justification}
          onChange={e => setJustification(e.target.value)}
        />
        {flags.map(flag => (
          <div key={flag.id} className="bg-gray-900 border border-red-800 p-4 rounded mb-2">
            <p className="text-red-400 font-bold">Risk: {flag.risk_score}/100 — {flag.status}</p>
            <p className="text-gray-300 text-sm mt-1">{flag.explanation}</p>
            <button
              onClick={() => overrideFlag(flag.id)}
              className="mt-2 px-3 py-1 bg-yellow-600 hover:bg-yellow-700 text-white text-sm rounded"
            >
              Override → VERIFIED
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Add route in `App.jsx`:**
```jsx
<Route path="/admin/dashboard" element={
  <RoleGuard role="admin"><AdminDashboard /></RoleGuard>
} />
```

---

## ADDITION 12 — UPDATED REQUIREMENTS.TXT

Add these to `backend/requirements.txt` if not already present:

```
cryptography>=42.0.0
slowapi>=0.1.9
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

---

## ADDITION 13 — GITIGNORE UPDATES

Add to `.gitignore` if not present:

```
benchmarks/results.json
*.pem
*_private_key*
.env
__pycache__/
.pytest_cache/
```

---

## TASK ORDER FOR CURSOR/ANTIGRAVITY

Implement in this exact order to avoid dependency issues:

1. Addition 10 — Refactor `compute_risk_score()` (everything else depends on it)
2. Addition 6 — Tests (verify refactor works)
3. Addition 4 — JWT logout + Redis blacklist
4. Addition 3 — Rate limiting
5. Addition 5 — CORS production guard
6. Addition 1 — ECDSA signing layer
7. Addition 7 — DisruptionEvents migration + model
8. Addition 8 — Admin portal backend
9. Addition 11 — Admin dashboard frontend
10. Addition 2 — Benchmarking module
11. Addition 9 — Seeder script
12. Addition 12 — Update requirements.txt
13. Addition 13 — Update .gitignore

---

**ChainMed_UpdatePrompt.md**
*Additions only. Nothing here duplicates the master prompt.*
*Use with Cursor, Antigravity, or any AI pointing at github.com/Anish05s/ChainMed*
