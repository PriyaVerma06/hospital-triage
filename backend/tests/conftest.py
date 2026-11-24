"""
Shared pytest fixtures and test helpers for authentication and role-based testing.
Provides seed_test_users helper and role-specific auth header fixtures.
"""

from pathlib import Path
import sys
import os
import secrets
os.environ.setdefault("TRIAGE_SECRET_KEY", "test-only-secret-key-not-for-deployment-123456789")
import pytest
from sqlalchemy.orm import Session

# Ensure backend/ is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from auth import create_access_token, hash_password

TEST_PASSWORD = secrets.token_urlsafe(24)
from models import User, UserRole


def seed_test_users(db: Session):
    """Populate isolated test database with synthetic clinical users only."""
    pw_hash = hash_password(TEST_PASSWORD)
    users = [
        User(id=2, username="nurse1", password_hash=pw_hash, full_name="Nurse Sarah Jenkins", role=UserRole.NURSE, doctor_id=None, is_active=True),
        User(id=3, username="nurse2", password_hash=pw_hash, full_name="Nurse David Kim", role=UserRole.NURSE, doctor_id=None, is_active=True),
        User(id=4, username="dr1", password_hash=pw_hash, full_name="Dr. Sarah Chen", role=UserRole.DOCTOR, doctor_id=1, is_active=True),
        User(id=5, username="dr2", password_hash=pw_hash, full_name="Dr. Marcus Vance", role=UserRole.DOCTOR, doctor_id=2, is_active=True),
        User(id=6, username="dr3", password_hash=pw_hash, full_name="Dr. Elena Rostova", role=UserRole.DOCTOR, doctor_id=3, is_active=True),
        User(id=7, username="dr4", password_hash=pw_hash, full_name="Dr. James Wilson", role=UserRole.DOCTOR, doctor_id=4, is_active=True),
        User(id=8, username="dr5", password_hash=pw_hash, full_name="Dr. Priya Patel", role=UserRole.DOCTOR, doctor_id=5, is_active=True),
    ]
    db.add_all(users)
    db.commit()


@pytest.fixture
def nurse_headers():
    """Authorization headers for triage nurse."""
    user = User(id=2, username="nurse1", role=UserRole.NURSE, doctor_id=None)
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(nurse_headers):
    """Compatibility alias for older tests; ADMIN access no longer exists."""
    return nurse_headers


class DoctorHeadersDict(dict):
    """Header dictionary that can also be called with doctor_id (e.g. doctor_headers(3))."""
    def __call__(self, doctor_id: int = 1):
        user = User(
            id=3 + doctor_id,
            username=f"dr{doctor_id}",
            role=UserRole.DOCTOR,
            doctor_id=doctor_id,
        )
        token = create_access_token(user)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def doctor_headers():
    """Authorization headers for physician (defaults to Dr. 1, callable as doctor_headers(id))."""
    user = User(id=4, username="dr1", role=UserRole.DOCTOR, doctor_id=1)
    token = create_access_token(user)
    return DoctorHeadersDict({"Authorization": f"Bearer {token}"})
