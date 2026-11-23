"""
SQLAlchemy models for the hospital triage system.
Includes Patient, Bed, Doctor, and AuditLog tables.
"""

from datetime import datetime
import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


# --- Enums ---

class PatientStatus(str, enum.Enum):
    """Lifecycle status of a patient in the triage workflow."""
    WAITING = "WAITING"
    ASSIGNED = "ASSIGNED"
    DISCHARGED = "DISCHARGED"


class BedWard(str, enum.Enum):
    """Hospital ward classification for beds."""
    ICU = "ICU"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"


class BedStatus(str, enum.Enum):
    """Availability status of hospital beds."""
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"


class DoctorSpecialty(str, enum.Enum):
    """Medical specialty of hospital doctors."""
    EMERGENCY = "Emergency"
    CARDIOLOGY = "Cardiology"
    GENERAL = "General"


class UserRole(str, enum.Enum):
    """User account authorization role."""
    NURSE = "NURSE"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


# --- Database Models ---

class Patient(Base):
    """Patient record containing demographics, triage vitals, and assignment details."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    symptoms = Column(Text, nullable=True)

    # Triage vital signs
    sbp = Column(Integer, nullable=True)       # Systolic blood pressure (mmHg)
    dbp = Column(Integer, nullable=True)       # Diastolic blood pressure (mmHg)
    hr = Column(Integer, nullable=True)        # Heart rate (bpm)
    spo2 = Column(Float, nullable=True)       # Oxygen saturation (%)
    temp = Column(Float, nullable=True)       # Temperature (°C)
    rr = Column(Integer, nullable=True)        # Respiratory rate (breaths/min)

    # Triage decision fields
    urgency_level = Column(Integer, nullable=True)   # Score 1 (highest) to 5 (lowest)
    reason_tags = Column(JSON, default=list, nullable=True)  # List of explanatory tags
    status = Column(Enum(PatientStatus), default=PatientStatus.WAITING, nullable=False)

    # Assignments (foreign keys)
    assigned_bed_id = Column(String, ForeignKey("beds.id"), nullable=True)
    assigned_doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    bed = relationship("Bed", back_populates="patients")
    doctor = relationship("Doctor", back_populates="patients")
    audit_logs = relationship("AuditLog", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")


class Bed(Base):
    """Hospital bed resource with ward location and equipment specs."""
    __tablename__ = "beds"

    id = Column(String, primary_key=True, index=True)  # e.g., "ICU-01", "ER-01"
    ward = Column(Enum(BedWard), nullable=False)
    has_ventilator = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(BedStatus), default=BedStatus.AVAILABLE, nullable=False)

    # Relationships
    patients = relationship("Patient", back_populates="bed")


class Doctor(Base):
    """Hospital physician on-duty for patient triage assignments."""
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(Enum(DoctorSpecialty), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    active_patients_count = Column(Integer, default=0, nullable=False)

    # Relationships
    patients = relationship("Patient", back_populates="doctor")
    alerts = relationship("Alert", back_populates="doctor")
    user = relationship("User", back_populates="doctor", uselist=False)


class AuditLog(Base):
    """Audit log entry capturing state transitions and clinical events per patient."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    event = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="audit_logs")


class Alert(Base):
    """Clinical emergency alert dispatched to doctors and nurses/admins."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    level = Column(Integer, nullable=False)
    message = Column(String, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="alerts")
    doctor = relationship("Doctor", back_populates="alerts")


class User(Base):
    """System user account for authentication and role-based access control."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    doctor = relationship("Doctor", back_populates="user")


