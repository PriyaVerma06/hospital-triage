"""
Tests for Step 7 Analytics endpoints (/analytics/*).
Covers all 5 analytics endpoints with correctness checks and edge cases.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, get_db
from main import app
from models import Bed, BedStatus, BedWard, Doctor, DoctorSpecialty, Patient, PatientStatus
from tests.conftest import seed_test_users


# ---------------------------------------------------------------------------
# Test-scoped in-memory SQLite DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    seed_test_users(db)

    # Seed standard doctors and beds so resources endpoints don't 500
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


def _make_patient(test_db, **kwargs):
    """Helper to insert a minimal patient into the test DB."""
    defaults = dict(
        name="Test Patient", age=40, gender="M", symptoms="headache",
        sbp=120, dbp=80, hr=72, spo2=98.0, temp=37.0, rr=16,
        urgency_level=3, status=PatientStatus.WAITING,
        created_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    p = Patient(**defaults)
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# 1. Empty database → zeros, not errors
# ---------------------------------------------------------------------------

def test_summary_empty_db(admin_headers):
    resp = client.get("/analytics/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_patients"] == 0
    assert data["avg_wait_minutes"] == 0.0
    assert data["critical_count"] == 0


def test_triage_distribution_empty_db(nurse_headers):
    resp = client.get("/analytics/triage-distribution", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    # All 5 levels present with count=0
    assert len(data["distribution"]) == 5
    for entry in data["distribution"]:
        assert entry["count"] == 0


def test_wait_by_level_empty_db(doctor_headers):
    resp = client.get("/analytics/wait-by-level", headers=doctor_headers)
    assert resp.status_code == 200
    for entry in resp.json()["wait_by_level"]:
        assert entry["avg_wait_minutes"] == 0.0


def test_timeline_empty_db(admin_headers):
    resp = client.get("/analytics/timeline?hours=2", headers=admin_headers)
    assert resp.status_code == 200
    for entry in resp.json()["timeline"]:
        assert entry["arrivals"] == 0


def test_occupancy_no_error(admin_headers):
    """Occupancy uses live beds; should return valid data even with 0 patients."""
    resp = client.get("/analytics/occupancy", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "wards" in data
    assert "ICU" in data["wards"]


# ---------------------------------------------------------------------------
# 2. Triage distribution counts are correct
# ---------------------------------------------------------------------------

def test_triage_distribution_counts(admin_headers, test_db):
    _make_patient(test_db, urgency_level=1)
    _make_patient(test_db, urgency_level=1)
    _make_patient(test_db, urgency_level=3)
    _make_patient(test_db, urgency_level=5)

    resp = client.get("/analytics/triage-distribution", headers=admin_headers)
    assert resp.status_code == 200
    dist = {entry["level"]: entry["count"] for entry in resp.json()["distribution"]}
    assert dist[1] == 2
    assert dist[2] == 0
    assert dist[3] == 1
    assert dist[4] == 0
    assert dist[5] == 1


# ---------------------------------------------------------------------------
# 3. Wait-time math is correct
# ---------------------------------------------------------------------------

def test_wait_by_level_avg_correct(admin_headers, test_db):
    """
    Create two Level-2 patients:
    - p1: admitted 30 minutes ago, assigned_at = 10 min ago → wait = 20 min
    - p2: admitted 60 minutes ago, assigned_at = 20 min ago → wait = 40 min
    Expected avg = 30.0 minutes.
    """
    now = datetime.utcnow()
    p1 = _make_patient(test_db, urgency_level=2, status=PatientStatus.ASSIGNED,
                       created_at=now - timedelta(minutes=30),
                       assigned_at=now - timedelta(minutes=10))
    p2 = _make_patient(test_db, urgency_level=2, status=PatientStatus.ASSIGNED,
                       created_at=now - timedelta(minutes=60),
                       assigned_at=now - timedelta(minutes=20))
    # Set assigned_at directly (not via intake flow)
    test_db.query(Patient).filter(Patient.id == p1.id).update({"assigned_at": now - timedelta(minutes=10)})
    test_db.query(Patient).filter(Patient.id == p2.id).update({"assigned_at": now - timedelta(minutes=20)})
    test_db.commit()

    resp = client.get("/analytics/wait-by-level?hours=2", headers=admin_headers)
    assert resp.status_code == 200
    by_level = {e["level"]: e["avg_wait_minutes"] for e in resp.json()["wait_by_level"]}
    assert abs(by_level[2] - 30.0) < 1.0  # allow 1-min rounding tolerance


# ---------------------------------------------------------------------------
# 4. Occupancy percentages match bed states
# ---------------------------------------------------------------------------

def test_occupancy_percentages(admin_headers, test_db):
    """Mark 2 of 4 ICU beds OCCUPIED; expect 50% occupancy."""
    test_db.query(Bed).filter(Bed.id == "ICU-01").update({"status": BedStatus.OCCUPIED})
    test_db.query(Bed).filter(Bed.id == "ICU-02").update({"status": BedStatus.OCCUPIED})
    test_db.commit()

    resp = client.get("/analytics/occupancy", headers=admin_headers)
    assert resp.status_code == 200
    icu = resp.json()["wards"]["ICU"]
    assert icu["occupied"] == 2
    assert icu["available"] == 2
    assert icu["occupancy_pct"] == 50.0


# ---------------------------------------------------------------------------
# 5. Role access
# ---------------------------------------------------------------------------

def test_doctor_can_read_analytics(doctor_headers):
    resp = client.get("/analytics/summary", headers=doctor_headers)
    assert resp.status_code == 200


def test_nurse_can_read_analytics(nurse_headers):
    resp = client.get("/analytics/triage-distribution", headers=nurse_headers)
    assert resp.status_code == 200


def test_unauthenticated_gets_401():
    resp = client.get("/analytics/summary")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 6. Summary critical count
# ---------------------------------------------------------------------------

def test_summary_critical_count(admin_headers, test_db):
    _make_patient(test_db, urgency_level=1)
    _make_patient(test_db, urgency_level=2)
    _make_patient(test_db, urgency_level=4)

    resp = client.get("/analytics/summary", headers=admin_headers)
    data = resp.json()
    assert data["total_patients"] == 3
    assert data["critical_count"] == 2
    assert abs(data["escalation_rate_pct"] - 66.7) < 1.0
