"""Full reset + restore default test orgs and logins.

Run from backend folder:
  python scripts/reset_and_seed.py

Logins:
  manufacturer@chainmed.com  / ChainMed2026!  — Ravi Kumar
  supplier@chainmed.com    / ChainMed2026!  — Priya Sharma
  hospital@chainmed.com    / ChainMed2026!  — Dr. Anand Mehta
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from database import engine, SessionLocal
from models import Manufacturer, Supplier, Consumer, User
from auth.utils import hash_password

TABLES = [
    "handoff_records",
    "ai_flags",
    "shipments",
    "medicine_batches",
    "approval_logs",
    "stock_levels",
    "restock_requests",
    "notifications",
    "users",
    "manufacturers",
    "suppliers",
    "consumers",
    "disruption_events",
]

from auth.signing import generate_entity_keypair

mfg_keys = generate_entity_keypair()
sup_keys = generate_entity_keypair()
con_keys = generate_entity_keypair()

ENTITIES = {
    "manufacturer": Manufacturer(
        id="mfg-001",
        name="AzMed Pharma Ltd",
        license_number="AZM-LIC-001",
        country="India",
        public_key_pem=mfg_keys["public_key_pem"],
        private_key_pem=mfg_keys["private_key_pem"],
    ),
    "supplier": Supplier(
        id="sup-001",
        name="NorthEast Medical Supply",
        warehouse_location="Guwahati",
        country="India",
        public_key_pem=sup_keys["public_key_pem"],
        private_key_pem=sup_keys["private_key_pem"],
    ),
    "consumer": Consumer(
        id="con-001",
        name="Civil Hospital Guwahati",
        type="hospital",
        location="Guwahati",
        country="India",
        public_key_pem=con_keys["public_key_pem"],
        private_key_pem=con_keys["private_key_pem"],
    ),
}

from config import settings

ACCOUNTS = [
    {
        "email": "manufacturer@chainmed.com",
        "password": "ChainMed2026!",
        "full_name": "Ravi Kumar",
        "role": "manufacturer",
        "sub_role": "manufacturer_admin",
        "entity_id": "mfg-001",
    },
    {
        "email": "supplier@chainmed.com",
        "password": "ChainMed2026!",
        "full_name": "Priya Sharma",
        "role": "supplier",
        "sub_role": "supplier_manager",
        "entity_id": "sup-001",
    },
    {
        "email": "hospital@chainmed.com",
        "password": "ChainMed2026!",
        "full_name": "Dr. Anand Mehta",
        "role": "consumer",
        "sub_role": "hospital_officer",
        "entity_id": "con-001",
    },
    {
        "email": "admin_master@chainmed.com",
        "password": settings.ADMIN_MASTER_PASSWORD,
        "full_name": "God Mode Admin",
        "role": "admin",
        "sub_role": "admin_master",
        "entity_id": None,
    },
    {
        "email": "admin_manager@chainmed.com",
        "password": settings.ADMIN_MANAGER_PASSWORD,
        "full_name": "Compliance Admin",
        "role": "admin",
        "sub_role": "admin_manager",
        "entity_id": None,
    },
    {
        "email": "admin_dev@chainmed.com",
        "password": settings.ADMIN_DEV_PASSWORD,
        "full_name": "Technical Admin",
        "role": "admin",
        "sub_role": "admin_dev",
        "entity_id": None,
    },
]


def wipe():
    with engine.connect() as conn:
        for table in TABLES:
            conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
        conn.commit()


def seed():
    db = SessionLocal()
    try:
        db.add(ENTITIES["manufacturer"])
        db.add(ENTITIES["supplier"])
        db.add(ENTITIES["consumer"])
        db.flush()

        for acc in ACCOUNTS:
            keys = generate_entity_keypair()
            db.add(
                User(
                    email=acc["email"],
                    hashed_password=hash_password(acc["password"]),
                    full_name=acc["full_name"],
                    role=acc["role"],
                    sub_role=acc["sub_role"],
                    entity_id=acc["entity_id"],
                    public_key_pem=keys["public_key_pem"],
                    private_key_pem=keys["private_key_pem"],
                )
            )
        db.commit()
    finally:
        db.close()


def main():
    print("Wiping database…")
    wipe()
    print("Seeding orgs + users…")
    seed()
    print("Done. Fresh DB with same logins:")
    for acc in ACCOUNTS:
        print(f"  {acc['email']}  ({acc['full_name']})  password: {acc['password']}")
    print("\nEntity IDs: mfg-001 | sup-001 | con-001")


if __name__ == "__main__":
    main()
