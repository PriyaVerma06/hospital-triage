"""
Test suite for the resource allocation engine in backend/allocation.py.
Verifies bed preference hierarchies, ventilator rules, provider capacity constraints,
waiting list management, and acuity-driven bed upgrades.
"""

from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend/ is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, get_db
from main import app
from models import Bed, BedStatus, BedWard, Doctor, DoctorSpecialty, Patient, PatientStatus

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_allocation_db():
    """Create fresh schema and seed 15 beds and 5 doctors for each allocation test."""
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    # 15 beds: 4 ICU (with ventilators), 5 EMERGENCY, 6 GENERAL
    beds = [
        *(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE) for i in range(1, 5)),
        *(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 6)),
        *(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 7)),
    ]
    # 5 doctors: 2 Emergency, 1 Cardiology, 2 General
    doctors = [
        Doctor(name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0),
        Doctor(name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
        Doctor(name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
    ]
    db.add_all(beds + doctors)
    db.commit()
    db.close()

    yield

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# --- Test Cases ---

def test_level_1_gets_icu_with_ventilator():
    """A Level 1 critical patient receives an ICU bed with ventilator."""
    patient_payload = {
        "name": "Critical Cardiac",
        "age": 65,
        "gender": "M",
        "symptoms": "Severe chest pain, unresponsive, gasping for air",
        "sbp": 75,
        "dbp": 50,
        "hr": 150,
        "spo2": 84.0,
        "temp": 37.2,
        "rr": 32,
    }
    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["urgency_level"] == 1
    assert data["status"] == "ASSIGNED"
    assert data["assigned_bed_id"] == "ICU-01"
    assert data["allocation"]["assigned"] is True
    assert data["allocation"]["bed_id"] == "ICU-01"

    # Verify audit log mentions ICU bed with ventilator
    audit_resp = client.get(f"/patients/{data['id']}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert any("Assigned to ICU-01 (ICU, ventilator)" in ev for ev in events)


def test_icu_full_level_1_falls_back_to_emergency():
    """
    When all 4 ICU beds are full, a 5th Level 1 patient falls back to an EMERGENCY bed
    and the audit log records that it was an alternative.
    """
    db = TestingSessionLocal()
    # Mark all 4 ICU beds as OCCUPIED
    for bed in db.query(Bed).filter(Bed.ward == BedWard.ICU).all():
        bed.status = BedStatus.OCCUPIED
    db.commit()
    db.close()

    # Patient is Level 1 due to critical hypotension (SBP 76) and tachycardia (HR 145),
    # but does not need a ventilator (SpO2 95, RR 20, not unconscious)
    patient_payload = {
        "name": "Level 1 Fallback Patient",
        "age": 58,
        "gender": "M",
        "symptoms": "Severe acute chest pain radiating to jaw",
        "sbp": 76,
        "dbp": 52,
        "hr": 145,
        "spo2": 95.0,
        "temp": 37.1,
        "rr": 20,
    }
    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["urgency_level"] == 1
    assert data["status"] == "ASSIGNED"
    # Should fall back to first available EMERGENCY bed
    assert data["assigned_bed_id"].startswith("ER-")

    # Verify audit log states it was an alternative
    audit_resp = client.get(f"/patients/{data['id']}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert any("Nearest alternative: EMERGENCY bed used because" in ev for ev in events)


def test_level_5_never_gets_icu_or_emergency():
    """A Level 5 non-urgent patient never gets an ICU or EMERGENCY bed."""
    # 1. With all beds free, Level 5 gets a GENERAL bed
    patient_payload = {
        "name": "Level 5 Routine",
        "age": 22,
        "gender": "M",
        "symptoms": "Prescription refill, feeling well",
        "sbp": 120,
        "dbp": 80,
        "hr": 70,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 14,
    }
    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["urgency_level"] in (4, 5)
    assert data["assigned_bed_id"].startswith("GEN-")

    # 2. Occupy all General beds, leaving ICU and Emergency completely free
    db = TestingSessionLocal()
    for bed in db.query(Bed).filter(Bed.ward == BedWard.GENERAL).all():
        bed.status = BedStatus.OCCUPIED
    db.commit()
    db.close()

    patient_payload2 = {
        "name": "Level 5 While Gen Full",
        "age": 23,
        "gender": "F",
        "symptoms": "Minor papercut on finger",
        "sbp": 118,
        "dbp": 78,
        "hr": 68,
        "spo2": 99.0,
        "temp": 36.5,
        "rr": 14,
    }
    resp2 = client.post("/patients", json=patient_payload2)
    assert resp2.status_code == 201
    data2 = resp2.json()
    # Must NOT be assigned to ICU or Emergency bed
    assert data2["status"] == "WAITING"
    assert data2["assigned_bed_id"] is None


def test_level_5_waitlisted_when_general_full():
    """When all General beds are full, a Level 5 patient is WAITING with a 'Waitlisted' audit entry."""
    db = TestingSessionLocal()
    for bed in db.query(Bed).filter(Bed.ward == BedWard.GENERAL).all():
        bed.status = BedStatus.OCCUPIED
    db.commit()
    db.close()

    patient_payload = {
        "name": "Waitlisted Mild Patient",
        "age": 29,
        "gender": "F",
        "symptoms": "Minor sprain from walking",
        "sbp": 120,
        "dbp": 80,
        "hr": 72,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 15,
    }
    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "WAITING"
    assert data["allocation"]["assigned"] is False

    # Verify Waitlisted audit log
    audit_resp = client.get(f"/patients/{data['id']}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert any("Waitlisted: no GENERAL bed available" in ev for ev in events)


def test_discharge_and_cleaning_to_available_auto_assigns_waiting():
    """
    Discharging a patient frees the bed (CLEANING), then setting the bed AVAILABLE
    auto-assigns the highest-priority waiting patient.
    """
    # 1. Fill all 6 General beds with patients
    for i in range(1, 7):
        p_data = {
            "name": f"Admitted Patient {i}",
            "age": 30 + i,
            "gender": "M",
            "symptoms": "Minor injury",
            "sbp": 120,
            "dbp": 80,
            "hr": 72,
            "spo2": 98.0,
            "temp": 36.7,
            "rr": 15,
        }
        res = client.post("/patients", json=p_data)
        assert res.json()["status"] == "ASSIGNED"

    # 2. Admit 7th patient -> must be waitlisted because all General beds are taken
    waiting_patient_payload = {
        "name": "Patient Waiting In Queue",
        "age": 42,
        "gender": "F",
        "symptoms": "Minor injury",
        "sbp": 122,
        "dbp": 80,
        "hr": 74,
        "spo2": 99.0,
        "temp": 36.8,
        "rr": 15,
    }
    wait_resp = client.post("/patients", json=waiting_patient_payload)
    waiting_id = wait_resp.json()["id"]
    assert wait_resp.json()["status"] == "WAITING"

    # 3. Discharge patient 1 (who holds GEN-01)
    discharge_resp = client.put("/patients/1/discharge")
    assert discharge_resp.status_code == 200

    # Bed GEN-01 is now CLEANING
    db = TestingSessionLocal()
    gen1 = db.query(Bed).filter(Bed.id == "GEN-01").first()
    assert gen1.status == BedStatus.CLEANING
    db.close()

    # Waiting patient is still WAITING while bed is CLEANING
    p_check = client.get(f"/patients/{waiting_id}").json()
    assert p_check["status"] == "WAITING"

    # 4. Mark GEN-01 as AVAILABLE (e.g. sanitation finished)
    put_bed_resp = client.put("/beds/GEN-01/status", json={"status": "AVAILABLE"})
    assert put_bed_resp.status_code == 200

    # Auto-allocation should have triggered: waiting patient is now ASSIGNED to GEN-01!
    p_assigned = client.get(f"/patients/{waiting_id}").json()
    assert p_assigned["status"] == "ASSIGNED"
    assert p_assigned["assigned_bed_id"] == "GEN-01"


def test_doctor_max_capacity_skipped():
    """A doctor with 5 active patients is skipped in favor of another available doctor."""
    db = TestingSessionLocal()
    # Set Dr. Sarah Chen (Emergency) to maximum capacity (5 patients)
    dr_chen = db.query(Doctor).filter(Doctor.name == "Dr. Sarah Chen").first()
    dr_chen.active_patients_count = 5
    db.commit()
    db.close()

    # Admit an Emergency-preference patient (Level 1 non-cardiac)
    patient_payload = {
        "name": "Emergency Patient",
        "age": 45,
        "gender": "M",
        "symptoms": "Severe trauma, laceration",
        "sbp": 74,
        "dbp": 48,
        "hr": 145,
        "spo2": 95.0,
        "temp": 37.0,
        "rr": 20,
    }
    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ASSIGNED"

    # Verify Dr. Sarah Chen was skipped, and Dr. Marcus Vance was assigned instead
    db = TestingSessionLocal()
    dr_vance = db.query(Doctor).filter(Doctor.name == "Dr. Marcus Vance").first()
    assert data["assigned_doctor_id"] == dr_vance.id
    db.close()


def test_reprioritize_general_to_level_1_moves_to_icu():
    """
    Re-prioritizing a General-bed patient to Level 1 moves them to an ICU bed
    when one is free, sets old bed to CLEANING, and records the move in AuditLog.
    """
    # 1. Admit mild patient -> assigned to GEN-01
    patient_payload = {
        "name": "Patient Acuity Deterioration",
        "age": 52,
        "gender": "M",
        "symptoms": "Mild headache",
        "sbp": 120,
        "dbp": 80,
        "hr": 74,
        "spo2": 98.0,
        "temp": 36.8,
        "rr": 16,
    }
    resp = client.post("/patients", json=patient_payload)
    patient_id = resp.json()["id"]
    initial_bed = resp.json()["assigned_bed_id"]
    assert initial_bed.startswith("GEN-")

    # 2. Re-prioritize vitals to Level 1 critical values
    critical_vitals = {
        "sbp": 72,
        "dbp": 46,
        "hr": 150,
        "spo2": 85.0,
        "temp": 37.4,
        "rr": 32,
    }
    update_resp = client.put(f"/patients/{patient_id}/vitals", json=critical_vitals)
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert update_data["urgency_level"] == 1
    assert update_data["level_changed"] is True
    # Bed upgraded to ICU
    assert update_data["assigned_bed_id"] == "ICU-01"

    # 3. Verify old General bed was transitioned to CLEANING
    db = TestingSessionLocal()
    old_bed = db.query(Bed).filter(Bed.id == initial_bed).first()
    assert old_bed.status == BedStatus.CLEANING
    new_bed = db.query(Bed).filter(Bed.id == "ICU-01").first()
    assert new_bed.status == BedStatus.OCCUPIED
    db.close()

    # 4. Verify AuditLog records the move
    audit_resp = client.get(f"/patients/{patient_id}/audit")
    events = [entry["event"] for entry in audit_resp.json()]
    assert any(f"Moved from {initial_bed} to ICU-01 after re-prioritization" in ev for ev in events)
