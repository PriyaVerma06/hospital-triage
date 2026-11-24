"""
Test suite for Authentication, Role-Based Access Control (RBAC), and Protected WebSockets.
Verifies login flow, token validation, permission matrix enforcement, doctor-specific alert scoping,
user management access controls, and WebSocket token authentication.
"""

from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import starlette.websockets

# Ensure backend/ is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from auth import create_access_token
from tests.conftest import seed_test_users, TEST_PASSWORD
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
def setup_auth_db():
    """Create fresh schema, seed standard resources & users, and clear WebSocket connections."""
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
    # 4 ICU beds with ventilators, 5 ER beds, 6 General beds
    for i in range(1, 5):
        db.add(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE))
    for i in range(1, 6):
        db.add(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE))
    for i in range(1, 7):
        db.add(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE))

    # 5 on-duty doctors
    docs = [
        Doctor(id=1, name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(id=2, name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
        Doctor(id=3, name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0),
        Doctor(id=4, name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
        Doctor(id=5, name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
    ]
    db.add_all(docs)
    db.commit()

    # Seed isolated synthetic clinical users for this test only
    seed_test_users(db)
    db.close()

    yield

    manager.connections.clear()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def test_login_success_and_wrong_password():
    """Correct login returns access token and user info; incorrect credentials return 401."""
    # 1. Correct credentials for nurse1
    resp = client.post("/auth/login", data={"username": "nurse1", "password": TEST_PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "nurse1"
    assert data["user"]["role"] == "NURSE"
    assert "password_hash" not in data["user"]

    # 2. Wrong password returns 401
    resp_wrong_pw = client.post("/auth/login", data={"username": "nurse1", "password": "wrongpassword"})
    assert resp_wrong_pw.status_code == 401
    assert "Incorrect username or password" in resp_wrong_pw.json()["detail"]

    # 3. Non-existent user returns 401
    resp_wrong_user = client.post("/auth/login", data={"username": "nobody", "password": TEST_PASSWORD})
    assert resp_wrong_user.status_code == 401


def test_admin_role_cannot_sign_in_or_use_protected_apis():
    """Legacy ADMIN accounts are rejected even if a row still exists in the database."""
    db = TestingSessionLocal()
    admin = User(
        id=99,
        username="legacy_admin_test",
        password_hash=__import__("auth").hash_password(TEST_PASSWORD),
        full_name="Legacy Admin",
        role=UserRole.ADMIN,
        doctor_id=None,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    admin_token = create_access_token(admin)
    db.close()

    login_resp = client.post(
        "/auth/login",
        data={"username": "legacy_admin_test", "password": TEST_PASSWORD},
    )
    assert login_resp.status_code == 401

    protected_resp = client.get(
        "/patients",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert protected_resp.status_code == 403


def test_request_without_token_or_garbage_token():
    """Unauthenticated requests or requests with invalid tokens return 401 Unauthorized."""
    # 1. Missing token
    resp_no_token = client.get("/patients")
    assert resp_no_token.status_code == 401

    # 2. Garbage token
    resp_garbage = client.get("/patients", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert resp_garbage.status_code == 401


def test_nurse_can_update_bed_status(nurse_headers):
    """Authorized clinical staff can update operational bed status."""
    resp = client.put("/beds/ICU-01/status", json={"status": "CLEANING"}, headers=nurse_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLEANING"


def test_user_management_routes_are_not_exposed(nurse_headers):
    """There are no HTTP user-management or public registration endpoints."""
    assert client.post("/users", json={}).status_code == 404
    assert client.get("/users", headers=nurse_headers).status_code == 404
    assert client.post("/auth/register", json={}).status_code == 404


def test_doctor_alerts_scoping_and_acknowledgement(doctor_headers, admin_headers):
    """
    Doctor sees only their own alerts in GET /alerts, and receives 403 when attempting
    to acknowledge an alert assigned to another doctor.
    """
    db = TestingSessionLocal()
    patient = Patient(
        name="Alert Scope Patient",
        age=55,
        gender="M",
        symptoms="Test symptoms",
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

    # Alert for Doctor 1
    alert_doc1 = Alert(patient_id=patient.id, doctor_id=1, level=1, message="Alert for Doctor 1", acknowledged=False)
    # Alert for Doctor 2
    alert_doc2 = Alert(patient_id=patient.id, doctor_id=2, level=1, message="Alert for Doctor 2", acknowledged=False)
    db.add_all([alert_doc1, alert_doc2])
    db.commit()
    db.refresh(alert_doc1)
    db.refresh(alert_doc2)
    doc1_alert_id = alert_doc1.id
    doc2_alert_id = alert_doc2.id
    db.close()

    # Doctor 1 queries alerts -> only sees their own
    resp1 = client.get("/alerts", headers=doctor_headers(1))
    assert resp1.status_code == 200
    doc1_alerts = resp1.json()
    assert len(doc1_alerts) == 1
    assert doc1_alerts[0]["id"] == doc1_alert_id

    # Doctor 2 queries alerts -> only sees their own
    resp2 = client.get("/alerts", headers=doctor_headers(2))
    assert resp2.status_code == 200
    doc2_alerts = resp2.json()
    assert len(doc2_alerts) == 1
    assert doc2_alerts[0]["id"] == doc2_alert_id

    # Doctor 1 tries to acknowledge Doctor 2's alert -> 403 Forbidden
    forbidden_ack = client.put(f"/alerts/{doc2_alert_id}/acknowledge", headers=doctor_headers(1))
    assert forbidden_ack.status_code == 403
    assert "only permitted to acknowledge alerts assigned to themselves" in forbidden_ack.json()["detail"]

    # Doctor 1 acknowledges own alert -> 200 OK
    own_ack = client.put(f"/alerts/{doc1_alert_id}/acknowledge", headers=doctor_headers(1))
    assert own_ack.status_code == 200
    assert own_ack.json()["acknowledged"] is True



def test_auth_me_profile_never_exposes_password_hash(nurse_headers):
    """GET /auth/me returns current user profile and never exposes password_hash."""
    resp = client.get("/auth/me", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "nurse1"
    assert data["role"] == "NURSE"
    assert data["full_name"] == "Nurse Sarah Jenkins"
    assert "password_hash" not in data


def test_websocket_auth():
    """
    WebSocket /ws rejects connections with missing or invalid tokens (code 4401);
    accepts valid tokens and routes doctor-targeted alerts only to the assigned doctor.
    """
    # 1. Reject missing token
    with pytest.raises(starlette.websockets.WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pass
    assert exc_info.value.code == 4401

    # 2. Reject invalid token
    with pytest.raises(starlette.websockets.WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?token=invalid.jwt.token"):
            pass
    assert exc_info.value.code == 4401

    # 3. Connect successfully with Doctor 3 (Cardiology) and Doctor 4 (General)
    doc3_user = User(id=6, username="dr3", role=UserRole.DOCTOR, doctor_id=3)
    doc3_token = create_access_token(doc3_user)

    doc4_user = User(id=7, username="dr4", role=UserRole.DOCTOR, doctor_id=4)
    doc4_token = create_access_token(doc4_user)

    with client.websocket_connect(f"/ws?token={doc3_token}") as ws_cardiology, \
         client.websocket_connect(f"/ws?token={doc4_token}") as ws_general:

        # Test ping/pong keepalive
        ws_cardiology.send_text("ping")
        assert ws_cardiology.receive_text() == "pong"

        # Admit a Level 1 cardiac patient assigned to Doctor 3
        nurse_user = User(id=2, username="nurse1", role=UserRole.NURSE, doctor_id=None)
        nurse_token = create_access_token(nurse_user)
        payload = {
            "name": "Live Auth WS Cardiac",
            "age": 60,
            "gender": "M",
            "symptoms": "Severe crushing chest pain, diaphoresis",
            "sbp": 80,
            "dbp": 50,
            "hr": 140,
            "spo2": 88.0,
            "temp": 37.0,
            "rr": 28,
        }
        create_resp = client.post("/patients", json=payload, headers={"Authorization": f"Bearer {nurse_token}"})
        assert create_resp.status_code == 201
        assert create_resp.json()["assigned_doctor_id"] == 3

        # Doctor 3 receives alert
        received_alert = None
        for _ in range(5):
            event = ws_cardiology.receive_json()
            if event.get("type") == "alert":
                received_alert = event
                break

        assert received_alert is not None
        assert received_alert["doctor_id"] == 3
        assert "CRITICAL" in received_alert["message"]
