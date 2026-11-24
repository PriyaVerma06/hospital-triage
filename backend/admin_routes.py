"""
Admin management API for the hospital triage system.
All routes require ADMIN role. Covers Bed CRUD, Doctor CRUD, Shift scheduling,
shift-apply logic, and admin action log retrieval.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from allocation import allocate_waiting
from alerts import check_and_alert_assignment
from auth import get_current_user, require_roles
from database import get_db
from models import (
    AdminLog,
    Bed,
    BedStatus,
    BedWard,
    Doctor,
    Patient,
    Shift,
    User,
    UserRole,
)
from realtime import publish
from schemas import (
    AdminLogOut,
    BedCreate,
    BedOut,
    BedUpdate,
    DoctorCreate,
    DoctorOut,
    DoctorOutWithWarning,
    DoctorUpdate,
    ShiftApplyResult,
    ShiftCreate,
    ShiftOut,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

# ---------------------------------------------------------------------------
# Helper: record an admin action in the AdminLog table
# ---------------------------------------------------------------------------

def _log_admin_action(db: Session, user_id: Optional[int], action: str) -> None:
    """Append an AdminLog entry and commit immediately."""
    db.add(AdminLog(user_id=user_id, action=action, timestamp=datetime.utcnow()))
    db.commit()


# ---------------------------------------------------------------------------
# Bed management
# ---------------------------------------------------------------------------

@router.post("/beds", response_model=BedOut, status_code=201)
def create_bed(
    bed_in: BedCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Create a new hospital bed. 409 if bed ID already exists.
    For ICU beds, has_ventilator defaults to True when not specified.
    After creation, waiting patients are automatically re-allocated.
    """
    if db.query(Bed).filter(Bed.id == bed_in.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bed with ID '{bed_in.id}' already exists.",
        )

    # Default ventilator: True for ICU, False otherwise
    has_vent = bed_in.has_ventilator
    if has_vent is None:
        has_vent = (bed_in.ward == BedWard.ICU)

    bed = Bed(id=bed_in.id, ward=bed_in.ward, has_ventilator=has_vent, status=BedStatus.AVAILABLE)
    db.add(bed)
    db.commit()
    db.refresh(bed)

    _log_admin_action(db, current_user.id, f"Created bed {bed.id} (ward={bed.ward.value})")

    # Try to allocate waiting patients now that capacity increased
    newly_assigned = allocate_waiting(db)
    for p_id in newly_assigned:
        p = db.query(Patient).filter(Patient.id == p_id).first()
        if p:
            check_and_alert_assignment(db, p)

    publish({"type": "resources_changed"})
    publish({"type": "queue_changed"})

    db.refresh(bed)
    return bed


@router.put("/beds/{bed_id}", response_model=BedOut)
def update_bed(
    bed_id: str,
    bed_in: BedUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update bed ward or ventilator status.
    Returns 409 if the bed is currently OCCUPIED (clinical safety guard).
    """
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail=f"Bed '{bed_id}' not found.")

    if bed.status == BedStatus.OCCUPIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify an OCCUPIED bed. Discharge the patient first.",
        )

    if bed_in.ward is not None:
        bed.ward = bed_in.ward
    if bed_in.has_ventilator is not None:
        bed.has_ventilator = bed_in.has_ventilator

    db.commit()
    db.refresh(bed)

    _log_admin_action(db, current_user.id, f"Updated bed {bed.id}")
    publish({"type": "resources_changed"})
    return bed


@router.delete("/beds/{bed_id}", status_code=204)
def delete_bed(
    bed_id: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Delete a bed. Returns 409 if the bed is currently OCCUPIED.
    """
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail=f"Bed '{bed_id}' not found.")

    if bed.status == BedStatus.OCCUPIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an OCCUPIED bed. Discharge the patient first.",
        )

    db.delete(bed)
    db.commit()
    _log_admin_action(db, current_user.id, f"Deleted bed {bed_id}")
    publish({"type": "resources_changed"})


# ---------------------------------------------------------------------------
# Doctor management
# ---------------------------------------------------------------------------

@router.post("/doctors", response_model=DoctorOut, status_code=201)
def create_doctor(
    doc_in: DoctorCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Create a new hospital doctor.
    After creation, waiting patients are automatically re-allocated.
    """
    doctor = Doctor(
        name=doc_in.name,
        specialty=doc_in.specialty,
        is_available=doc_in.is_available,
        active_patients_count=0,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    _log_admin_action(db, current_user.id, f"Created doctor {doctor.id} ({doctor.name})")

    newly_assigned = allocate_waiting(db)
    for p_id in newly_assigned:
        p = db.query(Patient).filter(Patient.id == p_id).first()
        if p:
            check_and_alert_assignment(db, p)

    publish({"type": "resources_changed"})
    publish({"type": "queue_changed"})

    db.refresh(doctor)
    return doctor


@router.put("/doctors/{doctor_id}", response_model=DoctorOutWithWarning)
def update_doctor(
    doctor_id: int,
    doc_in: DoctorUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update doctor properties.
    If setting is_available=False while doctor has active patients, the update
    is allowed but a warning message is included in the response.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail=f"Doctor {doctor_id} not found.")

    warning: Optional[str] = None

    if doc_in.name is not None:
        doctor.name = doc_in.name
    if doc_in.specialty is not None:
        doctor.specialty = doc_in.specialty
    if doc_in.is_available is not None:
        # Warn (don't block) if setting unavailable while handling patients
        if not doc_in.is_available and doctor.active_patients_count > 0:
            warning = (
                f"Doctor set unavailable while managing {doctor.active_patients_count} "
                "active patient(s). Existing assignments are preserved."
            )
        doctor.is_available = doc_in.is_available

        # If going available, attempt to allocate waiting patients
        if doc_in.is_available:
            newly_assigned = allocate_waiting(db)
            for p_id in newly_assigned:
                p = db.query(Patient).filter(Patient.id == p_id).first()
                if p:
                    check_and_alert_assignment(db, p)

    db.commit()
    db.refresh(doctor)
    _log_admin_action(db, current_user.id, f"Updated doctor {doctor_id}")
    publish({"type": "resources_changed"})
    publish({"type": "queue_changed"})

    return DoctorOutWithWarning(
        id=doctor.id,
        name=doctor.name,
        specialty=doctor.specialty,
        is_available=doctor.is_available,
        active_patients_count=doctor.active_patients_count,
        warning=warning,
    )


@router.delete("/doctors/{doctor_id}", status_code=204)
def delete_doctor(
    doctor_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Delete a doctor. Returns 409 if doctor currently has active patients.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail=f"Doctor {doctor_id} not found.")

    if doctor.active_patients_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Doctor {doctor_id} has {doctor.active_patients_count} active patient(s). Reassign before deleting.",
        )

    db.delete(doctor)
    db.commit()
    _log_admin_action(db, current_user.id, f"Deleted doctor {doctor_id}")
    publish({"type": "resources_changed"})


# ---------------------------------------------------------------------------
# Shift management
# ---------------------------------------------------------------------------

@router.post("/shifts", response_model=ShiftOut, status_code=201)
def create_shift(
    shift_in: ShiftCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Schedule a shift for a doctor.
    Returns 400 if end_time <= start_time.
    Returns 409 if an overlapping shift already exists for that doctor.
    """
    if shift_in.end_time <= shift_in.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time.",
        )

    doctor = db.query(Doctor).filter(Doctor.id == shift_in.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail=f"Doctor {shift_in.doctor_id} not found.")

    # Check for overlapping shift: existing.start < new.end AND existing.end > new.start
    overlap = db.query(Shift).filter(
        Shift.doctor_id == shift_in.doctor_id,
        Shift.start_time < shift_in.end_time,
        Shift.end_time > shift_in.start_time,
    ).first()
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shift overlaps with existing shift (ID={overlap.id}) for doctor {shift_in.doctor_id}.",
        )

    shift = Shift(
        doctor_id=shift_in.doctor_id,
        start_time=shift_in.start_time,
        end_time=shift_in.end_time,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)

    _log_admin_action(db, current_user.id, f"Created shift {shift.id} for doctor {shift_in.doctor_id}")
    return shift


@router.get("/shifts", response_model=List[ShiftOut])
def list_shifts(
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD), returns shifts overlapping that day"),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    List shifts. Optionally filter by doctor_id and/or date (YYYY-MM-DD).
    A shift is included if it overlaps any part of the given date in UTC.
    """
    query = db.query(Shift)
    if doctor_id is not None:
        query = query.filter(Shift.doctor_id == doctor_id)

    if date is not None:
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD format.")
        from datetime import timedelta
        day_end = day_start + timedelta(days=1)
        # Overlaps the day: shift.start < day_end AND shift.end > day_start
        query = query.filter(Shift.start_time < day_end, Shift.end_time > day_start)

    return query.order_by(Shift.start_time.asc()).all()


@router.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(
    shift_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Delete a scheduled shift by ID."""
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail=f"Shift {shift_id} not found.")

    db.delete(shift)
    db.commit()
    _log_admin_action(db, current_user.id, f"Deleted shift {shift_id}")


@router.post("/shifts/apply", response_model=List[ShiftApplyResult])
def apply_shifts(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Apply current shift coverage to doctor availability.
    For each doctor:
      - If they have a shift covering NOW → set is_available = True
      - If they have shifts but none covering NOW → set is_available = False
      - If they have NO shifts defined at all → leave unchanged
    Returns list of changes made.
    """
    now = datetime.utcnow()
    all_doctors = db.query(Doctor).all()
    changes: List[ShiftApplyResult] = []

    for doctor in all_doctors:
        # Does ANY shift exist for this doctor?
        has_any_shift = db.query(Shift).filter(Shift.doctor_id == doctor.id).first()
        if has_any_shift is None:
            continue  # No shifts defined – skip

        # Check if a shift covers right now
        covering = db.query(Shift).filter(
            Shift.doctor_id == doctor.id,
            Shift.start_time <= now,
            Shift.end_time > now,
        ).first()

        new_avail = covering is not None
        if doctor.is_available != new_avail:
            doctor.is_available = new_avail
            changes.append(ShiftApplyResult(doctor_id=doctor.id, name=doctor.name, changed_to=new_avail))

    if changes:
        db.commit()
        newly_assigned = allocate_waiting(db)
        for p_id in newly_assigned:
            p = db.query(Patient).filter(Patient.id == p_id).first()
            if p:
                check_and_alert_assignment(db, p)
        publish({"type": "resources_changed"})
        publish({"type": "queue_changed"})

    _log_admin_action(db, current_user.id, f"Applied shifts: {len(changes)} doctor(s) updated")
    return changes


# ---------------------------------------------------------------------------
# Admin action logs
# ---------------------------------------------------------------------------

@router.get("/logs", response_model=List[AdminLogOut])
def list_admin_logs(
    limit: int = Query(50, ge=1, le=1000, description="Max entries to return"),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve recent admin action log entries, newest first."""
    return (
        db.query(AdminLog)
        .order_by(AdminLog.timestamp.desc(), AdminLog.id.desc())
        .limit(limit)
        .all()
    )
