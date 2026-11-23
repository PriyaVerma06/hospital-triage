"""
FastAPI application for the hospital emergency triage system.
Provides RESTful APIs for patient intake, triage execution, resource allocation,
queue management, and audit trail recording.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from allocation import (
    MAX_PATIENTS_PER_DOCTOR,
    allocate_waiting,
    assign_patient,
    release_patient_resources,
    try_upgrade_bed,
)
from database import Base, engine, get_db
from models import AuditLog, Bed, BedStatus, BedWard, Doctor, Patient, PatientStatus
from schemas import (
    AllocateRunResponse,
    AllocationResult,
    AuditLogOut,
    BedOut,
    BedStatusUpdate,
    DoctorAvailabilityUpdate,
    DoctorOut,
    PatientCreate,
    PatientCreateResponse,
    PatientOut,
    QueuePatientOut,
    ResourcesSummary,
    VitalsUpdate,
    VitalsUpdateResponse,
    WardBedCounts,
)
from triage_service import run_triage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: ensure database tables are initialized on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Hospital Triage System API",
    description="Emergency department patient triage, vital tracking, and resource allocation API.",
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
    records initial triage in AuditLog, attempts resource allocation, and adds to queue.
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

    # 3. Write initial triage audit log
    audit_entry = AuditLog(
        patient_id=db_patient.id,
        event=f"Initial Triage: Level {urgency_level}",
        timestamp=datetime.utcnow(),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(db_patient)

    # 4. Resource Allocation Engine (Step 4)
    alloc_dict = assign_patient(db, db_patient)
    if alloc_dict["assigned"]:
        # TODO Step 5: send alert to assigned doctor
        pass

    # Build response with prediction confidence and allocation details
    patient_data = PatientOut.model_validate(db_patient).model_dump()
    return PatientCreateResponse(
        **patient_data,
        confidence=confidence,
        allocation=AllocationResult(**alloc_dict),
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
    record re-prioritization event, and re-evaluate bed assignment.
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

    # Record appropriate audit log
    if level_changed:
        audit_event = f"Re-prioritized from Level {previous_level} to Level {new_urgency}"
    else:
        audit_event = f"Vitals updated, Level {new_urgency} unchanged"

    db.add(AuditLog(patient_id=patient.id, event=audit_event, timestamp=datetime.utcnow()))
    db.commit()
    db.refresh(patient)

    # Resource allocation re-evaluation (Step 4)
    alloc_result = None
    if patient.status == PatientStatus.WAITING:
        # Patient was waitlisted, attempt allocation with updated vitals/acuity
        alloc_result = assign_patient(db, patient)
        if alloc_result["assigned"]:
            # TODO Step 5: send alert to assigned doctor
            pass
    elif patient.status == PatientStatus.ASSIGNED and level_changed and new_urgency < previous_level:
        # Patient acuity worsened (e.g. 4 -> 1): attempt bed upgrade
        alloc_result = try_upgrade_bed(db, patient)
        # TODO Step 5: send alert to assigned doctor

    patient_data = PatientOut.model_validate(patient).model_dump()
    return VitalsUpdateResponse(
        **patient_data,
        previous_level=previous_level,
        level_changed=level_changed,
        allocation=alloc_result,
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
    """
    Discharge a patient: marks status as DISCHARGED, releases allocated bed (set to CLEANING)
    and doctor load, then triggers allocation for remaining waiting patients.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    patient.status = PatientStatus.DISCHARGED
    db.add(AuditLog(patient_id=patient.id, event="Patient discharged", timestamp=datetime.utcnow()))
    db.commit()

    # Step 4: Release resources and re-allocate to waiting patients
    release_patient_resources(db, patient)
    allocate_waiting(db)

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


# --- Hospital Resources & Allocation Management ---

@app.get(
    "/beds",
    response_model=List[BedOut],
    tags=["Resources"],
)
def list_beds(db: Session = Depends(get_db)):
    """Retrieve list of hospital beds and current statuses."""
    return db.query(Bed).order_by(Bed.id.asc()).all()


@app.put(
    "/beds/{bed_id}/status",
    response_model=BedOut,
    tags=["Resources"],
)
def update_bed_status(
    bed_id: str,
    status_in: BedStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update bed status (AVAILABLE, OCCUPIED, CLEANING).
    When set back to AVAILABLE, automatically allocates waiting patients.
    """
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bed with ID {bed_id} not found",
        )

    bed.status = status_in.status
    db.commit()
    db.refresh(bed)

    if bed.status == BedStatus.AVAILABLE:
        allocate_waiting(db)
        db.refresh(bed)

    return bed


@app.get(
    "/doctors",
    response_model=List[DoctorOut],
    tags=["Resources"],
)
def list_doctors(db: Session = Depends(get_db)):
    """Retrieve list of hospital doctors and availability statuses."""
    return db.query(Doctor).order_by(Doctor.id.asc()).all()


@app.put(
    "/doctors/{doctor_id}/availability",
    response_model=DoctorOut,
    tags=["Resources"],
)
def update_doctor_availability(
    doctor_id: int,
    avail_in: DoctorAvailabilityUpdate,
    db: Session = Depends(get_db),
):
    """
    Update doctor availability.
    When set back to True, automatically allocates waiting patients.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with ID {doctor_id} not found",
        )

    doctor.is_available = avail_in.is_available
    db.commit()
    db.refresh(doctor)

    if doctor.is_available:
        allocate_waiting(db)
        db.refresh(doctor)

    return doctor


@app.get(
    "/resources/summary",
    response_model=ResourcesSummary,
    tags=["Resources"],
)
def get_resources_summary(db: Session = Depends(get_db)):
    """
    Retrieve live summary of hospital resources: available/occupied/cleaning beds per ward,
    free ventilators, available doctors with capacity, and count of waiting patients.
    """
    all_beds = db.query(Bed).all()
    wards = [BedWard.ICU.value, BedWard.EMERGENCY.value, BedWard.GENERAL.value]
    beds_by_ward = {
        w: WardBedCounts(available=0, occupied=0, cleaning=0, total=0) for w in wards
    }

    free_ventilators = 0
    for b in all_beds:
        ward_key = b.ward.value
        if ward_key in beds_by_ward:
            beds_by_ward[ward_key].total += 1
            if b.status == BedStatus.AVAILABLE:
                beds_by_ward[ward_key].available += 1
                if b.has_ventilator:
                    free_ventilators += 1
            elif b.status == BedStatus.OCCUPIED:
                beds_by_ward[ward_key].occupied += 1
            elif b.status == BedStatus.CLEANING:
                beds_by_ward[ward_key].cleaning += 1

    all_doctors = db.query(Doctor).all()
    doctors_available = sum(
        1 for d in all_doctors if d.is_available and d.active_patients_count < MAX_PATIENTS_PER_DOCTOR
    )

    patients_waiting = (
        db.query(Patient).filter(Patient.status == PatientStatus.WAITING).count()
    )

    return ResourcesSummary(
        beds_by_ward=beds_by_ward,
        free_ventilators=free_ventilators,
        doctors_available=doctors_available,
        total_doctors=len(all_doctors),
        patients_waiting=patients_waiting,
    )


@app.post(
    "/allocate/run",
    response_model=AllocateRunResponse,
    tags=["Allocation"],
)
def run_manual_allocation(db: Session = Depends(get_db)):
    """Manually execute waiting queue allocation algorithm and return assigned patient IDs."""
    assigned_ids = allocate_waiting(db)
    return AllocateRunResponse(
        assigned_patient_ids=assigned_ids,
        count=len(assigned_ids),
    )
