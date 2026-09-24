import os
os.environ["DATABASE_URL"] = "sqlite:///./test_patients.db"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

VALID = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "05/12/1995",
    "sex": "Female",
    "phone_number": "732-555-1234",
    "address_line_1": "20 Main Street",
    "city": "Somerset",
    "state": "NJ",
    "zip_code": "08873"
}

def test_create_and_get_patient():
    r = client.post("/patients", json=VALID)
    assert r.status_code == 201
    data = r.json()["data"]
    patient_id = data["patient_id"]
    r2 = client.get(f"/patients/{patient_id}")
    assert r2.status_code == 200
    assert r2.json()["data"]["first_name"] == "Jane"

def test_reject_future_dob():
    payload = {**VALID, "date_of_birth": "12/31/2999", "phone_number": "2015551298"}
    r = client.post("/patients", json=payload)
    assert r.status_code == 422
    assert r.json()["error"] is not None

def test_reject_invalid_phone():
    payload = {**VALID, "phone_number": "123"}
    r = client.post("/patients", json=payload)
    assert r.status_code == 422

def test_update_filter_and_soft_delete():
    payload = {**VALID, "phone_number": "9735550111", "last_name": "Taylor"}
    created = client.post("/patients", json=payload)
    assert created.status_code == 201
    patient_id = created.json()["data"]["patient_id"]
    updated = client.put(f"/patients/{patient_id}", json={"city": "Jersey City"})
    assert updated.status_code == 200
    assert updated.json()["data"]["city"] == "Jersey City"
    filtered = client.get("/patients", params={"phone_number": "973-555-0111"})
    assert filtered.status_code == 200
    assert any(p["patient_id"] == patient_id for p in filtered.json()["data"])
    deleted = client.delete(f"/patients/{patient_id}")
    assert deleted.status_code == 200
    missing = client.get(f"/patients/{patient_id}")
    assert missing.status_code == 404
    assert missing.json()["error"] is not None
