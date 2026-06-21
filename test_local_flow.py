import requests

BASE_URL = "http://localhost:8000"

def get_token(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]

# 1. Login Manufacturer
mfg_token = get_token("manufacturer@chainmed.com", "ChainMed2026!")
mfg_headers = {"Authorization": f"Bearer {mfg_token}"}

# 2. Create Batch
batch_data = {
    "name": "Amoxycillin (500mg) + Clavulanic Acid (125mg)",
    "batch_number": "BATCH001",
    "quantity": 10000,
    "manufacturing_date": "2026-01-01",
    "expiry_date": "2029-06-20",
    "pieces_per_pack": 1,
    "pack_size": "10 strips"
}
r1 = requests.post(f"{BASE_URL}/manufacturer/batches", headers=mfg_headers, json=batch_data)
batch_id = r1.json()["id"]

# 4. Dispatch to SUP-001
dispatch_data = {
    "batch_id": batch_id,
    "to_entity_id": "sup-001",
    "quantity": 2000
}
r2 = requests.post(f"{BASE_URL}/manufacturer/shipments", headers=mfg_headers, json=dispatch_data)
shipment_id = r2.json()["id"]

# 5. Login Supplier
sup_token = get_token("supplier@chainmed.com", "ChainMed2026!")
sup_headers = {"Authorization": f"Bearer {sup_token}"}

# 6. Verify Shipment
verify_data = {
    "quantity_reported": 2000,
    "expiry_reported": "2029-06-20T00:00:00",
    "temp_reported": 24,
    "notes": "Verified"
}
r3 = requests.post(f"{BASE_URL}/supplier/shipments/{shipment_id}/verify", headers=sup_headers, json=verify_data)
print("Verify:", r3.status_code, r3.text)
