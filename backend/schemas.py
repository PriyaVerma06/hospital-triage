"""
Pydantic schemas for the hospital triage FastAPI application.
Defines request validation and response serialization models.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from models import BedStatus, BedWard, DoctorSpecialty, PatientStatus


# --- Vitals Base ---

class VitalsBase(BaseModel):
    """Vital signs with clinically validated ranges."""
    sbp: int = Field(
        ...,
        ge=50,
        le=300,
        description="Systolic blood pressure (50 to 300 mmHg)",
    )
    dbp: int = Field(
        ...,
        ge=30,
        le=200,
        description="Diastolic blood pressure (30 to 200 mmHg)",
    )
    hr: int = Field(
        ...,
        ge=20,
        le=250,
        description="Heart rate / pulse (20 to 250 bpm)",
    )
    spo2: float = Field(
        ...,
        ge=50.0,
        le=100.0,
        description="Blood oxygen saturation (50.0% to 100.0%)",
    )
    temp: float = Field(
        ...,
        ge=30.0,
        le=45.0,
        description="Body temperature in Celsius (30.0 to 45.0 °C)",
    )
    rr: int = Field(
        ...,
        ge=4,
        le=60,
        description="Respiratory rate (4 to 60 breaths/min)",
    )


# --- Request Schemas ---

class PatientCreate(VitalsBase):
    """Intake schema for admitting a new patient to the emergency triage."""
    name: str = Field(..., min_length=1, max_length=150, description="Patient full name")
    age: int = Field(..., ge=0, le=120, description="Age in years (0 to 120)")
    gender: Literal["M", "F"] = Field(..., description="Gender ('M' or 'F')")
    symptoms: str = Field(default="", description="Free-text clinical symptoms description")


class VitalsUpdate(VitalsBase):
    """Schema for updating an existing patient's vital signs."""
    pass


# --- Response Schemas ---

class PatientOut(BaseModel):
    """Output representation of a patient record."""
    id: int
    name: str
    age: int
    gender: str
    symptoms: Optional[str] = None
    sbp: Optional[int] = None
    dbp: Optional[int] = None
    hr: Optional[int] = None
    spo2: Optional[float] = None
    temp: Optional[float] = None
    rr: Optional[int] = None
    urgency_level: Optional[int] = None
    reason_tags: Optional[List[str]] = Field(default_factory=list)
    status: PatientStatus
    assigned_bed_id: Optional[str] = None
    assigned_doctor_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientCreateResponse(PatientOut):
    """Response returned upon patient intake including ML model confidence."""
    confidence: Optional[float] = Field(None, description="Triage model prediction confidence")


class VitalsUpdateResponse(PatientOut):
    """Response returned upon updating vitals indicating re-prioritization status."""
    previous_level: Optional[int] = Field(None, description="Urgency level prior to vitals update")
    level_changed: bool = Field(False, description="Whether triage urgency level changed")


class QueuePatientOut(PatientOut):
    """Waiting queue representation enriched with triage color and elapsed wait time."""
    color: str = Field(..., description="Triage category color: 'RED' (1-2), 'YELLOW' (3), 'GREEN' (4-5)")
    wait_minutes: float = Field(..., description="Minutes elapsed since intake in WAITING state")


class AuditLogOut(BaseModel):
    """Output representation of a patient clinical/triage audit event."""
    id: int
    patient_id: int
    event: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class BedOut(BaseModel):
    """Output representation of a hospital bed resource."""
    id: str
    ward: BedWard
    has_ventilator: bool
    status: BedStatus

    model_config = ConfigDict(from_attributes=True)


class DoctorOut(BaseModel):
    """Output representation of a hospital physician."""
    id: int
    name: str
    specialty: DoctorSpecialty
    is_available: bool
    active_patients_count: int

    model_config = ConfigDict(from_attributes=True)
