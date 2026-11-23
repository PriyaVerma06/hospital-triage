"""
Integration and unit tests for the hospital triage FastAPI application.
Uses an isolated temporary SQLite database to avoid modifying triage.db.
"""

from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend/ is in sys.path when running tests
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, get_db
from main import app
from models import Bed, BedStatus, BedWard, Doctor, DoctorSpecialty

# Create in-memory SQLite database isolated for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh database tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed initial beds and doctors in the test DB
    db = TestingSessionLocal()
    db.add(Bed(id="ICU-01", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE))
    db.add(Bed(id="ER-01", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE))
    db.add(Doctor(name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0))
    db.commit()
    db.close()

    yield

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
client = TestClient(app)


# --- Test Cases ---

def test_health_endpoint():
    """GET /health should return 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_critical_patient():
    """Create a critical patient (SpO2 85, HR 150) -> level 1 with confidence."""
    payload = {
        "name": "Jane Critical",
        "age": 68,
        "gender": "F",
        "symptoms": "Severe chest pain, cannot breathe, collapsed and unresponsive",
        "sbp": 75,
        "dbp": 50,
        "hr": 150,
        "spo2": 85.0,
        "temp": 37.2,
        "rr": 30,
    }
    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Critical"
    assert data["urgency_level"] == 1
    assert data["status"] in ("WAITING", "ASSIGNED")
    assert "confidence" in data
    assert isinstance(data["confidence"], float)
    assert len(data["reason_tags"]) >= 1

    # Check that initial triage AuditLog entry was recorded
    patient_id = data["id"]
    audit_resp = client.get(f"/patients/{patient_id}/audit")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert len(audit_data) >= 1
    assert any("Initial Triage: Level 1" in entry["event"] for entry in audit_data)


def test_create_normal_patient():
    """Create a normal patient with stable vitals -> level 4 or 5."""
    payload = {
        "name": "John Healthy",
        "age": 24,
        "gender": "M",
        "symptoms": "Routine wellness checkup, feeling fine",
        "sbp": 120,
        "dbp": 80,
        "hr": 70,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 14,
    }
    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["urgency_level"] in (4, 5)
    assert data["status"] == "WAITING"


def test_queue_ordering_and_color():
    """
    GET /queue puts the critical patient first with color RED,
    and normal patient with color GREEN.
    """
    # Ensure ICU bed is occupied so critical patient waits in queue
    db = TestingSessionLocal()
    icu_bed = db.query(Bed).filter(Bed.id == "ICU-01").first()
    if icu_bed:
        icu_bed.status = BedStatus.OCCUPIED
        db.commit()
    db.close()

    # 1. Admit normal patient first (so created_at is earlier)
    normal_payload = {
        "name": "Patient Normal",
        "age": 25,
        "gender": "M",
        "symptoms": "Minor scrape on finger",
        "sbp": 120,
        "dbp": 80,
        "hr": 72,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 14,
    }
    client.post("/patients", json=normal_payload)

    # 2. Admit critical patient second
    critical_payload = {
        "name": "Patient Critical",
        "age": 62,
        "gender": "M",
        "symptoms": "Severe chest pain, unresponsive",
        "sbp": 70,
        "dbp": 45,
        "hr": 148,
        "spo2": 84.0,
        "temp": 37.0,
        "rr": 32,
    }
    client.post("/patients", json=critical_payload)

    # 3. Retrieve queue
    response = client.get("/queue")
    assert response.status_code == 200
    queue = response.json()
    assert len(queue) == 2

    # First in queue must be the critical patient (urgency 1) despite being admitted second
    assert queue[0]["name"] == "Patient Critical"
    assert queue[0]["urgency_level"] == 1
    assert queue[0]["color"] == "RED"
    assert "wait_minutes" in queue[0]
    assert queue[0]["wait_minutes"] >= 0.0

    # Second in queue must be the normal patient (urgency 4 or 5)
    assert queue[1]["name"] == "Patient Normal"
    assert queue[1]["urgency_level"] in (4, 5)
    assert queue[1]["color"] == "GREEN"


def test_put_vitals_re_prioritization():
    """
    PUT vitals on the normal patient with critical vitals:
    level_changed is true and the audit log records a re-prioritization entry.
    """
    # Create normal patient
    patient_payload = {
        "name": "Alex Transition",
        "age": 30,
        "gender": "F",
        "symptoms": "Mild headache",
        "sbp": 118,
        "dbp": 76,
        "hr": 74,
        "spo2": 98.0,
        "temp": 36.8,
        "rr": 15,
    }
    create_resp = client.post("/patients", json=patient_payload)
    patient_id = create_resp.json()["id"]
    initial_level = create_resp.json()["urgency_level"]
    assert initial_level in (4, 5)

    # Update with critical vitals
    critical_vitals = {
        "sbp": 72,
        "dbp": 48,
        "hr": 145,
        "spo2": 86.0,
        "temp": 37.5,
        "rr": 30,
    }
    put_resp = client.put(f"/patients/{patient_id}/vitals", json=critical_vitals)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["urgency_level"] == 1
    assert put_data["previous_level"] == initial_level
    assert put_data["level_changed"] is True

    # Verify audit log contains re-prioritization message
    audit_resp = client.get(f"/patients/{patient_id}/audit")
    assert audit_resp.status_code == 200
    events = [entry["event"] for entry in audit_resp.json()]
    expected_event = f"Re-prioritized from Level {initial_level} to Level 1"
    assert any(expected_event in ev for ev in events)


def test_put_vitals_unchanged():
    """Updating vitals without changing urgency level logs 'Vitals updated, Level X unchanged'."""
    patient_payload = {
        "name": "Sam Stable",
        "age": 32,
        "gender": "M",
        "symptoms": "Mild scrape",
        "sbp": 120,
        "dbp": 80,
        "hr": 72,
        "spo2": 99.0,
        "temp": 36.7,
        "rr": 14,
    }
    create_resp = client.post("/patients", json=patient_payload)
    patient_id = create_resp.json()["id"]

    # Update with similarly normal vitals
    new_vitals = {
        "sbp": 122,
        "dbp": 82,
        "hr": 74,
        "spo2": 99.0,
        "temp": 36.8,
        "rr": 15,
    }
    put_resp = client.put(f"/patients/{patient_id}/vitals", json=new_vitals)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["level_changed"] is False

    audit_resp = client.get(f"/patients/{patient_id}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert any("Vitals updated, Level" in ev and "unchanged" in ev for ev in events)


def test_invalid_input_validation_422():
    """Invalid input (e.g. SpO2 = 150 or invalid gender) returns HTTP 422."""
    # Test invalid SpO2 (> 100)
    invalid_spo2 = {
        "name": "Invalid Vitals",
        "age": 40,
        "gender": "M",
        "symptoms": "Cough",
        "sbp": 120,
        "dbp": 80,
        "hr": 75,
        "spo2": 150.0,  # Invalid: max is 100
        "temp": 37.0,
        "rr": 16,
    }
    resp1 = client.post("/patients", json=invalid_spo2)
    assert resp1.status_code == 422

    # Test invalid gender
    invalid_gender = {
        "name": "Invalid Gender",
        "age": 40,
        "gender": "OTHER",  # Invalid: must be "M" or "F"
        "sbp": 120,
        "dbp": 80,
        "hr": 75,
        "spo2": 98.0,
        "temp": 37.0,
        "rr": 16,
    }
    resp2 = client.post("/patients", json=invalid_gender)
    assert resp2.status_code == 422

    # Test invalid age (> 120)
    invalid_age = {
        "name": "Invalid Age",
        "age": 150,  # Invalid: max 120
        "gender": "F",
        "symptoms": "Old",
        "sbp": 120,
        "dbp": 80,
        "hr": 75,
        "spo2": 98.0,
        "temp": 37.0,
        "rr": 16,
    }
    resp3 = client.post("/patients", json=invalid_age)
    assert resp3.status_code == 422


def test_unknown_patient_404():
    """Requesting or updating an unknown patient ID returns HTTP 404."""
    fake_id = 999999
    assert client.get(f"/patients/{fake_id}").status_code == 404
    assert client.put(f"/patients/{fake_id}/vitals", json={
        "sbp": 120, "dbp": 80, "hr": 70, "spo2": 98.0, "temp": 37.0, "rr": 16
    }).status_code == 404
    assert client.put(f"/patients/{fake_id}/discharge").status_code == 404
    assert client.get(f"/patients/{fake_id}/audit").status_code == 404


def test_discharge_patient():
    """Discharging a patient sets status to DISCHARGED and removes them from /queue."""
    patient_payload = {
        "name": "Discharge Test",
        "age": 28,
        "gender": "F",
        "symptoms": "Sprain",
        "sbp": 118,
        "dbp": 78,
        "hr": 70,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 14,
    }
    create_resp = client.post("/patients", json=patient_payload)
    patient_id = create_resp.json()["id"]

    # Verify patient is in queue
    q_resp = client.get("/queue")
    assert any(p["id"] == patient_id for p in q_resp.json())

    # Discharge patient
    discharge_resp = client.put(f"/patients/{patient_id}/discharge")
    assert discharge_resp.status_code == 200
    assert discharge_resp.json()["status"] == "DISCHARGED"

    # Verify patient is no longer in /queue
    q_resp_after = client.get("/queue")
    assert not any(p["id"] == patient_id for p in q_resp_after.json())

    # Verify audit log contains discharge event
    audit_resp = client.get(f"/patients/{patient_id}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert "Patient discharged" in events


def test_list_resources():
    """GET /beds and GET /doctors return lists of resources."""
    beds_resp = client.get("/beds")
    assert beds_resp.status_code == 200
    assert isinstance(beds_resp.json(), list)
    assert len(beds_resp.json()) >= 1

    docs_resp = client.get("/doctors")
    assert docs_resp.status_code == 200
    assert isinstance(docs_resp.json(), list)
    assert len(docs_resp.json()) >= 1
