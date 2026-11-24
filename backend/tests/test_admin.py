"""
Tests for Step 7 Admin Management endpoints (/admin/*).
Covers Bed CRUD, Doctor CRUD, Shift scheduling, shifts/apply, and admin logs.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend/ is on path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, get_db
from main import app
from models import Bed, BedStatus, BedWard, Doctor, DoctorSpecialty, Patient, PatientStatus, Shift
from tests.conftest import seed_test_users


# ---------------------------------------------------------------------------
# Test-scoped in-memory SQLite DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def test_db():
    """Create a fresh in-memory SQLite DB for each test, seed users and resources."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Seed users, doctors, and beds
    seed_test_users(db)

    doctors = [
        Doctor(id=1, name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(id=2, name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(id=3, name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0),
        Doctor(id=4, name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
        Doctor(id=5, name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
    ]
    beds = [
        *(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE) for i in range(1, 5)),
        *(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 6)),
        *(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 7)),
    ]
    db.add_all(doctors + beds)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    db.close()


client = TestClient(app)


# ---------------------------------------------------------------------------
# Tests: Bed CRUD
# ---------------------------------------------------------------------------

def test_admin_create_bed(admin_headers):
    """Admin can create a new bed."""
    resp = client.post("/admin/beds", json={"id": "GEN-99", "ward": "GENERAL"}, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "GEN-99"
    assert data["ward"] == "GENERAL"
    assert data["has_ventilator"] is False   # ICU default only for ICU beds


def test_admin_create_bed_duplicate_409(admin_headers):
    """Creating a bed with an existing ID returns 409."""
    resp = client.post("/admin/beds", json={"id": "ICU-01", "ward": "ICU"}, headers=admin_headers)
    assert resp.status_code == 409


def test_nurse_cannot_create_bed(nurse_headers):
    """NURSE cannot create beds; expects 403."""
    resp = client.post("/admin/beds", json={"id": "GEN-99", "ward": "GENERAL"}, headers=nurse_headers)
    assert resp.status_code == 403


def test_cannot_edit_occupied_bed(admin_headers, test_db):
    """Editing an OCCUPIED bed returns 409."""
    test_db.query(Bed).filter(Bed.id == "GEN-01").update({"status": BedStatus.OCCUPIED})
    test_db.commit()

    resp = client.put("/admin/beds/GEN-01", json={"has_ventilator": True}, headers=admin_headers)
    assert resp.status_code == 409


def test_cannot_delete_occupied_bed(admin_headers, test_db):
    """Deleting an OCCUPIED bed returns 409."""
    test_db.query(Bed).filter(Bed.id == "GEN-01").update({"status": BedStatus.OCCUPIED})
    test_db.commit()

    resp = client.delete("/admin/beds/GEN-01", headers=admin_headers)
    assert resp.status_code == 409


def test_delete_available_bed(admin_headers):
    """Admin can delete an available bed."""
    resp = client.delete("/admin/beds/GEN-06", headers=admin_headers)
    assert resp.status_code == 204


def test_new_bed_allocates_waiting_patient(admin_headers, test_db):
    """
    If all GENERAL beds are OCCUPIED and a Level-4 patient is WAITING,
    adding a new GENERAL bed should auto-assign them.
    """
    # Occupy all 6 GENERAL beds
    for i in range(1, 7):
        test_db.query(Bed).filter(Bed.id == f"GEN-0{i}").update({"status": BedStatus.OCCUPIED})
    test_db.commit()

    # Admit a Level-4 patient (mocked: insert directly with WAITING + urgency_level=4)
    p = Patient(
        name="Test Patient", age=40, gender="M", symptoms="mild headache",
        sbp=120, dbp=80, hr=72, spo2=98.0, temp=37.0, rr=16,
        urgency_level=4, status=PatientStatus.WAITING,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    assert p.status == PatientStatus.WAITING

    # Add a new GENERAL bed → should trigger allocation
    resp = client.post("/admin/beds", json={"id": "GEN-NEW", "ward": "GENERAL"}, headers=admin_headers)
    assert resp.status_code == 201

    test_db.refresh(p)
    assert p.status == PatientStatus.ASSIGNED


# ---------------------------------------------------------------------------
# Tests: Doctor CRUD
# ---------------------------------------------------------------------------

def test_cannot_delete_doctor_with_active_patients(admin_headers, test_db):
    """Cannot delete a doctor with active patients; expects 409."""
    test_db.query(Doctor).filter(Doctor.id == 1).update({"active_patients_count": 2})
    test_db.commit()

    resp = client.delete("/admin/doctors/1", headers=admin_headers)
    assert resp.status_code == 409


def test_set_busy_doctor_unavailable_returns_warning(admin_headers, test_db):
    """Setting a busy doctor unavailable returns 200 with a warning field."""
    test_db.query(Doctor).filter(Doctor.id == 1).update({"active_patients_count": 3})
    test_db.commit()

    resp = client.put("/admin/doctors/1", json={"is_available": False}, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_available"] is False
    assert data["warning"] is not None
    assert "active patient" in data["warning"].lower()


def test_set_busy_doctor_available_no_warning(admin_headers, test_db):
    """Setting a doctor available returns no warning."""
    test_db.query(Doctor).filter(Doctor.id == 1).update({"is_available": False, "active_patients_count": 0})
    test_db.commit()

    resp = client.put("/admin/doctors/1", json={"is_available": True}, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_available"] is True
    assert data.get("warning") is None


# ---------------------------------------------------------------------------
# Tests: Shifts
# ---------------------------------------------------------------------------

def test_overlapping_shifts_return_409(admin_headers):
    """Creating a shift that overlaps an existing one returns 409."""
    now = datetime.utcnow()
    # Create first shift
    r1 = client.post("/admin/shifts", json={
        "doctor_id": 1,
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(hours=8)).isoformat(),
    }, headers=admin_headers)
    assert r1.status_code == 201

    # Overlapping shift
    r2 = client.post("/admin/shifts", json={
        "doctor_id": 1,
        "start_time": (now + timedelta(hours=4)).isoformat(),
        "end_time": (now + timedelta(hours=12)).isoformat(),
    }, headers=admin_headers)
    assert r2.status_code == 409


def test_end_before_start_returns_400(admin_headers):
    """Creating a shift where end_time <= start_time returns 400."""
    now = datetime.utcnow()
    r = client.post("/admin/shifts", json={
        "doctor_id": 1,
        "start_time": (now + timedelta(hours=8)).isoformat(),
        "end_time": now.isoformat(),
    }, headers=admin_headers)
    assert r.status_code == 400


def test_shifts_apply_marks_correct_availability(admin_headers, test_db):
    """
    Shifts/apply:
    - Doctor with current-covering shift → made available (if was unavailable)
    - Doctor with expired shift → made unavailable (if was available)
    - Doctor with no shifts → unchanged
    """
    now = datetime.utcnow()

    # Doctor 1: current shift covering now → should stay/become available
    test_db.add(Shift(doctor_id=1, start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=7)))
    # Doctor 2: past shift (expired) → should become unavailable
    test_db.add(Shift(doctor_id=2, start_time=now - timedelta(hours=10), end_time=now - timedelta(hours=2)))
    # Doctor 3: NO shifts → unchanged (is_available stays True)
    test_db.commit()

    # Set doctor 1 as unavailable so we can verify it gets toggled to True
    test_db.query(Doctor).filter(Doctor.id == 1).update({"is_available": False})
    test_db.commit()

    resp = client.post("/admin/shifts/apply", headers=admin_headers)
    assert resp.status_code == 200

    changes = {c["doctor_id"]: c["changed_to"] for c in resp.json()}

    # Doctor 1: had covering shift, was unavailable → should be changed to True
    assert changes.get(1) is True
    # Doctor 2: expired shift, was available → should be changed to False
    assert changes.get(2) is False
    # Doctor 3: no shifts → no change entry
    assert 3 not in changes

    # Verify Doctor 3's availability is unchanged (still True)
    d3 = test_db.query(Doctor).filter(Doctor.id == 3).first()
    assert d3.is_available is True


# ---------------------------------------------------------------------------
# Tests: Admin Logs
# ---------------------------------------------------------------------------

def test_admin_actions_appear_in_logs(admin_headers):
    """Admin actions (bed create, doctor update) are recorded in /admin/logs."""
    # Create a bed (generates a log entry)
    client.post("/admin/beds", json={"id": "LOG-TEST", "ward": "GENERAL"}, headers=admin_headers)

    resp = client.get("/admin/logs", headers=admin_headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    actions = [l["action"] for l in logs]
    assert any("LOG-TEST" in a for a in actions)


def test_nurse_cannot_read_admin_logs(nurse_headers):
    """NURSE cannot access /admin/logs; expects 403."""
    resp = client.get("/admin/logs", headers=nurse_headers)
    assert resp.status_code == 403
