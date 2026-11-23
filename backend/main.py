"""
FastAPI application for the hospital emergency triage system.
Provides RESTful APIs for patient intake, triage execution, queue management,
and audit trail recording.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import AuditLog, Bed, Doctor, Patient, PatientStatus
from schemas import (
    AuditLogOut,
    BedOut,
    DoctorOut,
    PatientCreate,
    PatientCreateResponse,
    PatientOut,
    QueuePatientOut,
    VitalsUpdate,
    VitalsUpdateResponse,
)
from triage_service import run_triage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: ensure database tables are initialized on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Hospital Triage System API",
    description="Emergency department patient triage, vital tracking, and queue management API.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for all origins to support frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_triage_color(urgency_level: Optional[int]) -> str:
    """Map triage urgency level (1-5) to display color."""
    if urgency_level in (1, 2):
        return "RED"
    elif urgency_level == 3:
        return "YELLOW"
    return "GREEN"


# --- Health Check ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify service availability."""
    return {"status": "ok"}


# --- Patient Intake & Management ---

@app.post(
    "/patients",
    response_model=PatientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"],
)
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
):
    """
    Intake a new emergency patient: validates inputs, evaluates triage with ML model,
    records the initial triage event in AuditLog, and adds to WAITING queue.
    """
    # 1. Run ML triage prediction
    urgency_level, reason_tags, confidence = run_triage(patient_in)

    # 2. Persist new Patient
    db_patient = Patient(
        name=patient_in.name,
        age=patient_in.age,
        gender=patient_in.gender,
        symptoms=patient_in.symptoms,
        sbp=patient_in.sbp,
        dbp=patient_in.dbp,
        hr=patient_in.hr,
        spo2=patient_in.spo2,
        temp=patient_in.temp,
        rr=patient_in.rr,
        urgency_level=urgency_level,
        reason_tags=reason_tags,
        status=PatientStatus.WAITING,
        created_at=datetime.utcnow(),
    )
    db.add(db_patient)
    db.flush()  # Obtain generated db_patient.id

    # TODO Step 4: Automatic bed and doctor assignment plugs in here

    # 3. Write initial triage audit log
    audit_entry = AuditLog(
        patient_id=db_patient.id,
        event=f"Initial Triage: Level {urgency_level}",
        timestamp=datetime.utcnow(),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(db_patient)

    # Build response with prediction confidence
    patient_data = PatientOut.model_validate(db_patient).model_dump()
    return PatientCreateResponse(
        **patient_data,
        confidence=confidence,
    )


@app.get(
    "/patients",
    response_model=List[PatientOut],
    tags=["Patients"],
)
def list_patients(
    status: Optional[PatientStatus] = Query(None, description="Filter patients by status"),
    db: Session = Depends(get_db),
):
    """
    List patients sorted by urgency_level ascending (1 first),
    then created_at ascending (longest wait first).
    """
    query = db.query(Patient)
    if status is not None:
        query = query.filter(Patient.status == status)

    return query.order_by(Patient.urgency_level.asc(), Patient.created_at.asc()).all()


@app.get(
    "/patients/{patient_id}",
    response_model=PatientOut,
    tags=["Patients"],
)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve details of a single patient by ID."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )
    return patient


@app.put(
    "/patients/{patient_id}/vitals",
    response_model=VitalsUpdateResponse,
    tags=["Patients"],
)
def update_patient_vitals(
    patient_id: int,
    vitals_in: VitalsUpdate,
    db: Session = Depends(get_db),
):
    """
    Update patient vital signs, re-run ML triage, update level and reason tags,
    and log re-prioritization event in AuditLog.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    previous_level = patient.urgency_level

    # Update patient vitals
    patient.sbp = vitals_in.sbp
    patient.dbp = vitals_in.dbp
    patient.hr = vitals_in.hr
    patient.spo2 = vitals_in.spo2
    patient.temp = vitals_in.temp
    patient.rr = vitals_in.rr

    # Re-run ML triage
    new_urgency, new_tags, _ = run_triage(patient)
    patient.urgency_level = new_urgency
    patient.reason_tags = new_tags

    level_changed = (new_urgency != previous_level)

    # TODO Step 4: Re-evaluate bed and doctor assignment plugs in here

    # Record appropriate audit log
    if level_changed:
        audit_event = f"Re-prioritized from Level {previous_level} to Level {new_urgency}"
    else:
        audit_event = f"Vitals updated, Level {new_urgency} unchanged"

    db.add(AuditLog(patient_id=patient.id, event=audit_event, timestamp=datetime.utcnow()))
    db.commit()
    db.refresh(patient)

    patient_data = PatientOut.model_validate(patient).model_dump()
    return VitalsUpdateResponse(
        **patient_data,
        previous_level=previous_level,
        level_changed=level_changed,
    )


@app.put(
    "/patients/{patient_id}/discharge",
    response_model=PatientOut,
    tags=["Patients"],
)
def discharge_patient(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """Discharge a patient and log the event."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    patient.status = PatientStatus.DISCHARGED
    # TODO Step 4: Release assigned bed and doctor plugs in here

    db.add(AuditLog(patient_id=patient.id, event="Patient discharged", timestamp=datetime.utcnow()))
    db.commit()
    db.refresh(patient)
    return patient


@app.get(
    "/patients/{patient_id}/audit",
    response_model=List[AuditLogOut],
    tags=["Audit"],
)
def get_patient_audit_log(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve audit history for a single patient, newest entries first."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    return (
        db.query(AuditLog)
        .filter(AuditLog.patient_id == patient_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )


# --- Queue Management ---

@app.get(
    "/queue",
    response_model=List[QueuePatientOut],
    tags=["Queue"],
)
def get_triage_queue(db: Session = Depends(get_db)):
    """
    Retrieve all WAITING patients in priority triage order (urgency 1 first, then wait time).
    Enriched with UI triage category color and wait time in minutes.
    """
    waiting_patients = (
        db.query(Patient)
        .filter(Patient.status == PatientStatus.WAITING)
        .order_by(Patient.urgency_level.asc(), Patient.created_at.asc())
        .all()
    )

    now = datetime.utcnow()
    queue_list = []
    for p in waiting_patients:
        wait_mins = round(max(0.0, (now - p.created_at).total_seconds() / 60.0), 1)
        color = _get_triage_color(p.urgency_level)
        patient_data = PatientOut.model_validate(p).model_dump()

        item = QueuePatientOut(
            **patient_data,
            color=color,
            wait_minutes=wait_mins,
        )
        queue_list.append(item)

    return queue_list


# --- Hospital Resources (Read-Only) ---

@app.get(
    "/beds",
    response_model=List[BedOut],
    tags=["Resources"],
)
def list_beds(db: Session = Depends(get_db)):
    """Retrieve list of hospital beds and current statuses."""
    return db.query(Bed).order_by(Bed.id.asc()).all()


@app.get(
    "/doctors",
    response_model=List[DoctorOut],
    tags=["Resources"],
)
def list_doctors(db: Session = Depends(get_db)):
    """Retrieve list of hospital doctors and availability statuses."""
    return db.query(Doctor).order_by(Doctor.id.asc()).all()
