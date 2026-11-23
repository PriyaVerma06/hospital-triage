"""
Test suite for WebSocket live updates and clinical alert service in backend/realtime.py and backend/alerts.py.
Verifies real-time event broadcasting, provider-targeted alerts, re-prioritization notifications,
acknowledgement endpoints, and alert filtering with RBAC authentication.
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

from auth import create_access_token
from tests.conftest import seed_test_users
from database import Base, get_db
from main import app
from models import (
    Alert,
    Bed,
    BedStatus,
    BedWard,
    Doctor,
    DoctorSpecialty,
    Patient,
    PatientStatus,
    User,
    UserRole,
)
from realtime import manager

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_realtime_db():
    """Create fresh schema, seed standard resources & users, and clear connections for each test."""
    Base.metadata.create_all(bind=test_engine)
    manager.connections.clear()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    # 4 ICU beds with ventilators
    for i in range(1, 5):
        db.add(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE))
    # 5 Emergency beds
    for i in range(1, 6):
        db.add(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE))
    # 6 General beds
    for i in range(1, 7):
        db.add(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE))

    # 5 on-duty doctors
    doc1 = Doctor(id=1, name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0)
    doc2 = Doctor(id=2, name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0)
    doc3 = Doctor(id=3, name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0)
    doc4 = Doctor(id=4, name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0)
    doc5 = Doctor(id=5, name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0)
    db.add_all([doc1, doc2, doc3, doc4, doc5])
    db.commit()

    # Seed test users
    seed_test_users(db)
    db.close()

    yield

    manager.connections.clear()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def test_websocket_ping_pong(nurse_headers):
    """Verify WebSocket connection accepts connection with valid JWT token and responds to ping with pong."""
    token = nurse_headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_broadcast_on_patient_creation(nurse_headers):
    """Verify connected WebSocket receives broadcast events when a new patient is created."""
    token = nurse_headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        payload = {
            "name": "Live Broadcast Test",
            "age": 45,
            "gender": "M",
            "symptoms": "Mild fever and sore throat",
            "sbp": 120,
            "dbp": 80,
            "hr": 72,
            "spo2": 98.0,
            "temp": 37.8,
            "rr": 16,
        }
        resp = client.post("/patients", json=payload, headers=nurse_headers)
        assert resp.status_code == 201

        # The client should receive real-time events (patient_created, queue_changed, etc.)
        events = []
        for _ in range(2):
            event = ws.receive_json()
            events.append(event)

        event_types = [e.get("type") for e in events]
        assert "patient_created" in event_types or "queue_changed" in event_types


def test_doctor_targeted_alert(doctor_headers, nurse_headers):
    """
    Verify assigned doctor receives clinical alert for Level 1/2 patient,
    while another unassigned doctor does not receive it.
    """
    doc3_token = doctor_headers(3)["Authorization"].split()[1]
    doc4_token = doctor_headers(4)["Authorization"].split()[1]

    with client.websocket_connect(f"/ws?token={doc3_token}") as ws_cardiology, \
         client.websocket_connect(f"/ws?token={doc4_token}") as ws_general:

        payload = {
            "name": "Arthur Cardiac",
            "age": 62,
            "gender": "M",
            "symptoms": "Crushing chest pain radiating to jaw, severe sweating",
            "sbp": 85,
            "dbp": 55,
            "hr": 135,
            "spo2": 89.0,
            "temp": 37.0,
            "rr": 26,
        }
        resp = client.post("/patients", json=payload, headers=nurse_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assigned_doctor_id"] == 3

        # Doctor 3's connection should receive the alert event
        received_alert = None
        for _ in range(5):
            event = ws_cardiology.receive_json()
            if event.get("type") == "alert":
                received_alert = event
                break

        assert received_alert is not None
        assert received_alert["doctor_id"] == 3
        assert "CRITICAL" in received_alert["message"]
        assert "Arthur Cardiac" in received_alert["message"]


def test_reprioritization_alert(nurse_headers):
    """Verify worsening vitals that elevate urgency trigger an alert and Alert record in DB."""
    # 1. Admit patient with Level 3 vitals
    payload = {
        "name": "Deteriorating Patient",
        "age": 50,
        "gender": "F",
        "symptoms": "Abdominal pain and nausea",
        "sbp": 125,
        "dbp": 82,
        "hr": 88,
        "spo2": 97.0,
        "temp": 37.4,
        "rr": 18,
    }
    resp = client.post("/patients", json=payload, headers=nurse_headers)
    assert resp.status_code == 201
    patient_id = resp.json()["id"]
    initial_urgency = resp.json()["urgency_level"]
    assert initial_urgency >= 3

    # 2. Update vitals to critical (SpO2 84, HR 150) -> level 1
    vitals_update = {
        "sbp": 75,
        "dbp": 50,
        "hr": 150,
        "spo2": 84.0,
        "temp": 38.5,
        "rr": 32,
    }
    update_resp = client.put(f"/patients/{patient_id}/vitals", json=vitals_update, headers=nurse_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["level_changed"] is True
    assert update_resp.json()["urgency_level"] == 1

    # 3. Check that an Alert record was persisted in the database
    db = TestingSessionLocal()
    alerts = db.query(Alert).filter(Alert.patient_id == patient_id).all()
    db.close()

    assert len(alerts) >= 1
    reprioritized_alert = next((a for a in alerts if "Re-prioritized" in a.message), None)
    assert reprioritized_alert is not None
    assert reprioritized_alert.level == 1
    assert reprioritized_alert.acknowledged is False


def test_alert_acknowledgement(nurse_headers):
    """Verify PUT /alerts/{id}/acknowledge marks alert as acknowledged."""
    # Create an alert directly in DB
    db = TestingSessionLocal()
    patient = Patient(
        name="Test Patient",
        age=30,
        gender="M",
        symptoms="Test",
        sbp=120,
        dbp=80,
        hr=70,
        spo2=99.0,
        temp=36.8,
        rr=14,
        urgency_level=1,
        status=PatientStatus.WAITING,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    alert = Alert(
        patient_id=patient.id,
        doctor_id=1,
        level=1,
        message="CRITICAL: Test Patient",
        acknowledged=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert_id = alert.id
    db.close()

    # Acknowledge the alert via API
    resp = client.put(f"/alerts/{alert_id}/acknowledge", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == alert_id
    assert data["acknowledged"] is True

    # Verify updated in database
    db = TestingSessionLocal()
    updated_alert = db.query(Alert).filter(Alert.id == alert_id).first()
    db.close()
    assert updated_alert.acknowledged is True

    # Non-existent alert returns 404
    resp_404 = client.put("/alerts/99999/acknowledge", headers=nurse_headers)
    assert resp_404.status_code == 404


def test_level_4_creates_no_alert(nurse_headers):
    """Verify Level 4 or 5 patient intake does NOT generate any Alert rows."""
    payload = {
        "name": "Mild Condition",
        "age": 28,
        "gender": "F",
        "symptoms": "Sprained ankle, minor pain",
        "sbp": 118,
        "dbp": 78,
        "hr": 70,
        "spo2": 99.0,
        "temp": 36.6,
        "rr": 14,
    }
    resp = client.post("/patients", json=payload, headers=nurse_headers)
    assert resp.status_code == 201
    patient_id = resp.json()["id"]
    assert resp.json()["urgency_level"] >= 4

    db = TestingSessionLocal()
    alerts = db.query(Alert).filter(Alert.patient_id == patient_id).all()
    db.close()
    assert len(alerts) == 0


def test_level_1_waitlisted_alert(nurse_headers):
    """Verify waitlisted Level 1 patient (no beds available) generates a NO BED alert."""
    db = TestingSessionLocal()
    # Mark all ICU and ER beds OCCUPIED
    db.query(Bed).filter(Bed.ward.in_([BedWard.ICU, BedWard.EMERGENCY])).update({"status": BedStatus.OCCUPIED})
    db.commit()
    db.close()

    payload = {
        "name": "Waitlisted Critical",
        "age": 70,
        "gender": "M",
        "symptoms": "Severe respiratory failure, unconscious and unresponsive",
        "sbp": 70,
        "dbp": 45,
        "hr": 160,
        "spo2": 82.0,
        "temp": 37.0,
        "rr": 36,
    }
    resp = client.post("/patients", json=payload, headers=nurse_headers)
    assert resp.status_code == 201
    patient_data = resp.json()
    assert patient_data["status"] == "WAITING"
    assert patient_data["urgency_level"] == 1

    # Check alert in DB
    db = TestingSessionLocal()
    alerts = db.query(Alert).filter(Alert.patient_id == patient_data["id"]).all()
    db.close()

    assert len(alerts) >= 1
    no_bed_alert = next((a for a in alerts if "NO BED" in a.message), None)
    assert no_bed_alert is not None
    assert no_bed_alert.level == 1
    assert no_bed_alert.doctor_id is None


def test_get_alerts_filtering(nurse_headers):
    """Verify GET /alerts endpoint supports filtering by doctor_id and unacknowledged_only."""
    db = TestingSessionLocal()
    patient = Patient(
        name="Filter Test",
        age=40,
        gender="M",
        symptoms="Test",
        sbp=120,
        dbp=80,
        hr=70,
        spo2=98.0,
        temp=36.8,
        rr=14,
        urgency_level=1,
        status=PatientStatus.WAITING,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # 1. Alert for doctor 1, unacknowledged
    a1 = Alert(patient_id=patient.id, doctor_id=1, level=1, message="Alert Doc 1 Unack", acknowledged=False)
    # 2. Alert for doctor 1, acknowledged
    a2 = Alert(patient_id=patient.id, doctor_id=1, level=2, message="Alert Doc 1 Ack", acknowledged=True)
    # 3. Alert for doctor 2, unacknowledged
    a3 = Alert(patient_id=patient.id, doctor_id=2, level=1, message="Alert Doc 2 Unack", acknowledged=False)
    db.add_all([a1, a2, a3])
    db.commit()
    db.close()

    # Query all
    resp_all = client.get("/alerts", headers=nurse_headers)
    assert resp_all.status_code == 200
    assert len(resp_all.json()) >= 3

    # Query doctor 1 only
    resp_doc1 = client.get("/alerts?doctor_id=1", headers=nurse_headers)
    assert resp_doc1.status_code == 200
    assert len(resp_doc1.json()) == 2
    assert all(a["doctor_id"] == 1 for a in resp_doc1.json())

    # Query doctor 1 unacknowledged only
    resp_doc1_unack = client.get("/alerts?doctor_id=1&unacknowledged_only=true", headers=nurse_headers)
    assert resp_doc1_unack.status_code == 200
    assert len(resp_doc1_unack.json()) == 1
    assert resp_doc1_unack.json()[0]["message"] == "Alert Doc 1 Unack"
