import requests

url = "https://chainmed-production-e8ff.up.railway.app/auth/login"
payload = {"email": "supplier@pharma.com", "password": "password123"}
r = requests.post(url, json=payload)
if r.status_code != 200:
    print("Login failed:", r.status_code, r.text)
    exit()

token = r.json()["access_token"]
print("Logged in!")

headers = {"Authorization": f"Bearer {token}", "Origin": "https://chainmed-supply.vercel.app"}

# Test restock requests
r2 = requests.get("https://chainmed-production-e8ff.up.railway.app/supplier/restock-requests/mine", headers=headers)
print("RESTOCK:", r2.status_code, r2.text)
