"""
Pydantic schemas for the hospital triage FastAPI application.
Defines request validation and response serialization models.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from models import BedStatus, BedWard, DoctorSpecialty, PatientStatus, UserRole


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


class BedStatusUpdate(BaseModel):
    """Schema for updating bed availability or cleaning status."""
    status: BedStatus = Field(..., description="Target bed status: AVAILABLE, OCCUPIED, or CLEANING")


class DoctorAvailabilityUpdate(BaseModel):
    """Schema for toggling doctor on-duty availability."""
    is_available: bool = Field(..., description="Doctor availability flag")


# --- Response Schemas ---

class AllocationResult(BaseModel):
    """Result of attempting to allocate bed and doctor resources."""
    assigned: bool = Field(..., description="True if both bed and doctor were successfully assigned")
    bed_id: Optional[str] = Field(None, description="Assigned bed identifier, if matched")
    doctor_id: Optional[int] = Field(None, description="Assigned doctor identifier, if matched")
    message: str = Field(..., description="Human-readable allocation or waitlist rationale")


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
    assigned_at: Optional[datetime] = None     # Step 7: first assignment timestamp
    discharged_at: Optional[datetime] = None   # Step 7: discharge timestamp

    model_config = ConfigDict(from_attributes=True)


class PatientCreateResponse(PatientOut):
    """Response returned upon patient intake including ML model confidence and allocation status."""
    confidence: Optional[float] = Field(None, description="Triage model prediction confidence")
    allocation: Optional[AllocationResult] = Field(None, description="Resource allocation outcome")


class VitalsUpdateResponse(PatientOut):
    """Response returned upon updating vitals indicating re-prioritization status."""
    previous_level: Optional[int] = Field(None, description="Urgency level prior to vitals update")
    level_changed: bool = Field(False, description="Whether triage urgency level changed")
    allocation: Optional[Dict] = Field(None, description="Resource allocation or bed upgrade outcome")


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


class AlertOut(BaseModel):
    """Output representation of a clinical emergency alert."""
    id: int
    patient_id: int
    doctor_id: Optional[int] = None
    level: int
    message: str
    acknowledged: bool
    created_at: datetime

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


class WardBedCounts(BaseModel):
    """Bed count breakdown for a single ward."""
    available: int = 0
    occupied: int = 0
    cleaning: int = 0
    total: int = 0


class ResourcesSummary(BaseModel):
    """Hospital resource utilization overview."""
    beds_by_ward: Dict[str, WardBedCounts]
    free_ventilators: int
    doctors_available: int
    total_doctors: int
    patients_waiting: int


class AllocateRunResponse(BaseModel):
    """Outcome of manually executing waiting queue allocation."""
    assigned_patient_ids: List[int]
    count: int


# --- User & Auth Schemas ---

class UserOut(BaseModel):
    """Output representation of a system user."""
    id: int
    username: str
    full_name: str
    role: UserRole
    doctor_id: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """OAuth2 access token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Step 7: Admin & Analytics Schemas ---

