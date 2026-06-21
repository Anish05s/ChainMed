"""
conftest.py — Shared test fixtures for ChainMed E2E tests
==========================================================

Uses an in-memory SQLite database per test session so:
  • Tests never touch the real Supabase database
  • Tests are fully isolated and repeatable
  • No network required — runs in CI with zero config
"""
import os
import sys
import pytest

# ── Path fix (allows `import` from backend root) ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Force test env BEFORE any app imports ─────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chainmed.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("KEY_ENCRYPTION_SECRET", "test-secret-key-for-ci-only-not-prod!")
os.environ.setdefault("SECRET_KEY", "test-jwt-secret-key-for-ci-only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ETHEREUM_RPC_URL", "")
os.environ.setdefault("ETHEREUM_PRIVATE_KEY", "")
os.environ.setdefault("CONTRACT_ADDRESS", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OPENWEATHER_API_KEY", "")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database import Base, get_db
from main import app

# ── SQLite test engine ─────────────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_chainmed.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables once per test session, drop on teardown."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Note: SQLite file deletion skipped on Windows (file locked by process).
    # The test DB is wiped by drop_all() above so no stale data persists.


@pytest.fixture(scope="session")
def client(setup_database):
    """FastAPI TestClient with the SQLite DB override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth helpers ───────────────────────────────────────────────────────────────

def register_and_login(client, email: str, password: str, role: str,
                       full_name: str, org_name: str, **extra) -> str:
    """Register an entity user and return their JWT token."""
    payload = {
        "email": email,
        "password": password,
        "role": role,
        "full_name": full_name,
        "organization_name": org_name,
        **extra,
    }
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 200, f"Registration failed for {email}: {r.text}"
    return r.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
