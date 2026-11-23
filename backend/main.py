"""
FastAPI application for the hospital emergency triage system.
Provides RESTful APIs and WebSocket live updates for patient intake, triage execution,
resource allocation, queue management, clinical alerts, user auth, and audit trail recording.

==========================================================================================
ROLE-BASED ACCESS CONTROL (RBAC) PERMISSION MATRIX
==========================================================================================
Route                                 Public   NURSE   DOCTOR   ADMIN   Notes
------------------------------------------------------------------------------------------
GET  /health                            ✓        ✓       ✓        ✓     Health check
POST /auth/login                        ✓        ✓       ✓        ✓     OAuth2 form login
GET  /auth/me                                    ✓       ✓        ✓     Authenticated user info
POST /users                                                       ✓     Create user (Admin only)
GET  /users                                                       ✓     List users (Admin only)
PUT  /users/{id}/active                                           ✓     Activate/deactivate user
POST /patients                                   ✓                ✓     Patient intake
GET  /patients                                   ✓       ✓        ✓     List patients
GET  /patients/{id}                              ✓       ✓        ✓     Patient details
PUT  /patients/{id}/vitals                       ✓       ✓        ✓     Update vitals
PUT  /patients/{id}/discharge                    ✓       ✓        ✓     Discharge patient
GET  /patients/{id}/audit                        ✓       ✓        ✓     Patient audit history
GET  /queue                                      ✓       ✓        ✓     Waiting queue
GET  /beds                                       ✓       ✓        ✓     List beds
PUT  /beds/{id}/status                                            ✓     Update bed status
GET  /doctors                                    ✓       ✓        ✓     List doctors
PUT  /doctors/{id}/availability                                   ✓     Toggle doctor availability
GET  /resources/summary                          ✓       ✓        ✓     Hospital resource summary
POST /allocate/run                                                ✓     Manual allocation trigger
GET  /alerts                                     ✓       ✓*       ✓     *DOCTOR forced to own alerts
PUT  /alerts/{id}/acknowledge                    ✓       ✓*       ✓     *DOCTOR can only ack own alerts
WS   /ws?token=<jwt>                             ✓       ✓        ✓     Authenticated live updates
==========================================================================================
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from alerts import (
    check_and_alert_assignment,
    check_and_alert_reprioritization,
)
from allocation import (
    MAX_PATIENTS_PER_DOCTOR,
    allocate_waiting,
    assign_patient,
    release_patient_resources,
    try_upgrade_bed,
)
from auth import (
    create_access_token,
    decode_token_for_ws,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from database import Base, engine, get_db
from models import (
    Alert,
    AuditLog,
    Bed,
    BedStatus,
    BedWard,
    Doctor,
    Patient,
    PatientStatus,
    User,
    UserRole,
)
from realtime import manager, publish, set_event_loop
from schemas import (
    AlertOut,
    AllocateRunResponse,
    AllocationResult,
    AuditLogOut,
    BedOut,
    BedStatusUpdate,
    DoctorAvailabilityUpdate,
    DoctorOut,
    LoginResponse,
    PatientCreate,
    PatientCreateResponse,
    PatientOut,
    QueuePatientOut,
    ResourcesSummary,
    UserActiveUpdate,
    UserCreate,
    UserOut,
    VitalsUpdate,
    VitalsUpdateResponse,
    WardBedCounts,
)
from triage_service import run_triage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: capture running event loop and initialize DB schema."""
    set_event_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Hospital Triage System API",
    description="Emergency department patient triage, vital tracking, resource allocation, and RBAC auth API.",
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


# --- WebSocket Live Updates ---

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT Bearer access token"),
):
    """
    WebSocket endpoint for authenticated real-time dashboard events and doctor-targeted alerts.
    Requires ?token=<jwt>. Decodes token and closes connection with code 4401 if invalid.
    """
    if not token:
        await websocket.close(code=4401)
        return

    user_info = decode_token_for_ws(token)
    if not user_info:
        await websocket.close(code=4401)
        return

    set_event_loop(asyncio.get_running_loop())
    await manager.connect(
        websocket,
        role=user_info["role"],
        doctor_id=user_info.get("doctor_id"),
    )
    try:
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# --- Health Check ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify service availability (Public)."""
    return {"status": "ok"}


# --- Authentication & User Management ---

@app.post(
    "/auth/login",
    response_model=LoginResponse,
    tags=["Authentication"],
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 username/password login endpoint (Public).
    Returns access token, token type, and authenticated user details.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@app.get(
    "/auth/me",
    response_model=UserOut,
    tags=["Authentication"],
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Retrieve profile of the currently authenticated user."""
    return current_user


@app.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["User Management"],
)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new user account (Admin only). Never exposes password hash."""
    # Check username uniqueness
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' already registered",
        )

    # Validate DOCTOR role doctor_id linkage
    if user_in.role == UserRole.DOCTOR:
        if not user_in.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="doctor_id is required for DOCTOR role",
            )
        doctor = db.query(Doctor).filter(Doctor.id == user_in.doctor_id).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with ID {user_in.doctor_id} not found",
            )
    else:
        if user_in.doctor_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="doctor_id should only be specified for DOCTOR role",
            )

    new_user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        doctor_id=user_in.doctor_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get(
    "/users",
    response_model=List[UserOut],
    tags=["User Management"],
)
def list_users(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """List all registered system users (Admin only)."""
    return db.query(User).order_by(User.id.asc()).all()


@app.put(
    "/users/{user_id}/active",
    response_model=UserOut,
    tags=["User Management"],
)
def update_user_active_status(
    user_id: int,
    active_in: UserActiveUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Activate or deactivate a user account (Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    user.is_active = active_in.is_active
    db.commit()
    db.refresh(user)
    return user


# --- Patient Intake & Management ---

@app.post(
    "/patients",
    response_model=PatientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"],
)
def create_patient(
    patient_in: PatientCreate,
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Intake a new emergency patient (NURSE, ADMIN): validates inputs, evaluates triage with ML model,
    records initial triage in AuditLog, attempts resource allocation, dispatches alerts,
    and broadcasts real-time events.
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

    # 4. Resource Allocation Engine
    alloc_dict = assign_patient(db, db_patient)

    # 5. Alert Dispatch
    check_and_alert_assignment(db, db_patient)

    # 6. Real-Time Event Broadcast
    publish({
        "type": "patient_created",
        "patient_id": db_patient.id,
        "urgency_level": db_patient.urgency_level,
        "status": db_patient.status.value,
    })
    publish({"type": "queue_changed"})
    publish({"type": "resources_changed"})
    if db_patient.assigned_bed_id:
        publish({"type": "bed_changed", "bed_id": db_patient.assigned_bed_id})

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
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
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
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
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
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update patient vital signs, re-run ML triage, update level and reason tags,
    record re-prioritization event, re-evaluate bed assignment, and send alerts if acuity worsened.
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

    # Trigger re-prioritization alert if acuity worsened
    check_and_alert_reprioritization(db, patient, previous_level=previous_level, new_urgency=new_urgency)

    # Resource allocation re-evaluation
    alloc_result = None
    if patient.status == PatientStatus.WAITING:
        alloc_result = assign_patient(db, patient)
        check_and_alert_assignment(db, patient)
    elif patient.status == PatientStatus.ASSIGNED and level_changed and new_urgency < previous_level:
        alloc_result = try_upgrade_bed(db, patient)

    # Broadcast real-time events
    publish({
        "type": "patient_updated",
        "patient_id": patient.id,
        "urgency_level": patient.urgency_level,
        "level_changed": level_changed,
        "previous_level": previous_level,
    })
    publish({"type": "queue_changed"})
    publish({"type": "resources_changed"})
    if patient.assigned_bed_id:
        publish({"type": "bed_changed", "bed_id": patient.assigned_bed_id})

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
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Discharge a patient: marks status as DISCHARGED, releases allocated bed (set to CLEANING)
    and doctor load, then triggers allocation and alerts for remaining waiting patients.
    Allowed: NURSE, DOCTOR, ADMIN.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    discharged_bed_id = patient.assigned_bed_id
    patient.status = PatientStatus.DISCHARGED
    db.add(AuditLog(patient_id=patient.id, event="Patient discharged", timestamp=datetime.utcnow()))
    db.commit()

    # Release resources and re-allocate to waiting patients
    release_patient_resources(db, patient)
    newly_assigned_ids = allocate_waiting(db)

    # Alert for any newly assigned critical patients
    for p_id in newly_assigned_ids:
        p_obj = db.query(Patient).filter(Patient.id == p_id).first()
        if p_obj:
            check_and_alert_assignment(db, p_obj)

    # Broadcast real-time updates
    publish({"type": "patient_discharged", "patient_id": patient.id})
    publish({"type": "queue_changed"})
    publish({"type": "resources_changed"})
    if discharged_bed_id:
        publish({"type": "bed_changed", "bed_id": discharged_bed_id})

    db.refresh(patient)
    return patient


@app.get(
    "/patients/{patient_id}/audit",
    response_model=List[AuditLogOut],
    tags=["Audit"],
)
def get_patient_audit_log(
    patient_id: int,
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
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
def get_triage_queue(
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
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


# --- Clinical Alerts ---

@app.get(
    "/alerts",
    response_model=List[AlertOut],
    tags=["Alerts"],
)
def list_alerts(
    doctor_id: Optional[int] = Query(None, description="Filter alerts by doctor ID"),
    unacknowledged_only: bool = Query(False, description="Filter only unacknowledged alerts"),
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retrieve hospital emergency alerts, newest entries first.
    DOCTOR role is restricted to seeing only their own alerts.
    """
    query = db.query(Alert)

    # Enforce role-based scoping for doctors
    if current_user.role == UserRole.DOCTOR:
        query = query.filter(Alert.doctor_id == current_user.doctor_id)
    else:
        if doctor_id is not None:
            query = query.filter(Alert.doctor_id == doctor_id)

    if unacknowledged_only:
        query = query.filter(Alert.acknowledged == False)

    return query.order_by(Alert.created_at.desc(), Alert.id.desc()).all()


@app.put(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertOut,
    tags=["Alerts"],
)
def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Acknowledge a clinical alert.
    NURSE and ADMIN can acknowledge any alert.
    DOCTOR can only acknowledge alerts assigned to their doctor_id (403 otherwise).
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )

    # Restrict doctor role to their own alerts
    if current_user.role == UserRole.DOCTOR:
        if alert.doctor_id != current_user.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors are only permitted to acknowledge alerts assigned to themselves",
            )

    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert


# --- Hospital Resources & Allocation Management ---

@app.get(
    "/beds",
    response_model=List[BedOut],
    tags=["Resources"],
)
def list_beds(
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
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
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update bed status (AVAILABLE, OCCUPIED, CLEANING) (Admin only).
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
        newly_assigned_ids = allocate_waiting(db)
        for p_id in newly_assigned_ids:
            p_obj = db.query(Patient).filter(Patient.id == p_id).first()
            if p_obj:
                check_and_alert_assignment(db, p_obj)
        db.refresh(bed)

    publish({"type": "bed_changed", "bed_id": bed.id, "status": bed.status.value})
    publish({"type": "resources_changed"})
    publish({"type": "queue_changed"})

    return bed


@app.get(
    "/doctors",
    response_model=List[DoctorOut],
    tags=["Resources"],
)
def list_doctors(
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
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
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update doctor availability (Admin only).
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
        newly_assigned_ids = allocate_waiting(db)
        for p_id in newly_assigned_ids:
            p_obj = db.query(Patient).filter(Patient.id == p_id).first()
            if p_obj:
                check_and_alert_assignment(db, p_obj)
        db.refresh(doctor)

    publish({"type": "resources_changed"})
    publish({"type": "queue_changed"})

    return doctor


@app.get(
    "/resources/summary",
    response_model=ResourcesSummary,
    tags=["Resources"],
)
def get_resources_summary(
    current_user: User = Depends(require_roles(UserRole.NURSE, UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
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
def run_manual_allocation(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Manually execute waiting queue allocation algorithm (Admin only) and return assigned patient IDs."""
    assigned_ids = allocate_waiting(db)
    for p_id in assigned_ids:
        p_obj = db.query(Patient).filter(Patient.id == p_id).first()
        if p_obj:
            check_and_alert_assignment(db, p_obj)

    if assigned_ids:
        publish({"type": "queue_changed"})
        publish({"type": "resources_changed"})

    return AllocateRunResponse(
        assigned_patient_ids=assigned_ids,
        count=len(assigned_ids),
    )
