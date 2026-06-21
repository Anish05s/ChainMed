import requests

url = "https://chainmed-production-e8ff.up.railway.app/auth/login"
payload = {"email": "jaydev@ompharma.com", "password": "password123"}
r = requests.post(url, json=payload)
if r.status_code != 200:
    print("Login failed:", r.status_code, r.text)
    exit()

token = r.json()["access_token"]
print("Logged in!")

headers = {"Authorization": f"Bearer {token}", "Origin": "https://chainmed-supply.vercel.app"}

r_inc = requests.get("https://chainmed-production-e8ff.up.railway.app/supplier/shipments/incoming", headers=headers)
shipments = r_inc.json()
print("Incoming shipments:", len(shipments))

if not shipments:
    print("No shipments to verify.")
    exit()

shipment_id = shipments[0]["id"]
print("Verifying shipment:", shipment_id)

payload_verify = {
    "quantity_reported": 2000,
    "expiry_reported": "2029-06-20T00:00:00",
    "temp_reported": 24,
    "notes": "Verified automatically"
}

r_verify = requests.post(f"https://chainmed-production-e8ff.up.railway.app/supplier/shipments/{shipment_id}/verify", headers=headers, json=payload_verify)
print("Verify result:", r_verify.status_code, r_verify.text)
