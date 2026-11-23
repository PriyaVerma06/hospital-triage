"""
Resource Allocation Engine for the hospital triage system.
Manages deterministic matching of patients to hospital beds and on-duty doctors
based on clinical urgency, equipment requirements, and provider capacity.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from models import AuditLog, Bed, BedStatus, BedWard, Doctor, DoctorSpecialty, Patient, PatientStatus

# --- Configuration Constants ---

MAX_PATIENTS_PER_DOCTOR = 5

# Bed preference orders by urgency level. First available match wins.
BED_PREFERENCES: Dict[int, List[Dict]] = {
    # Level 1: ICU with ventilator -> Any ICU -> Emergency
    1: [
        {"ward": BedWard.ICU, "require_ventilator": True, "label": "ICU bed with ventilator"},
        {"ward": BedWard.ICU, "require_ventilator": False, "label": "ICU bed"},
        {"ward": BedWard.EMERGENCY, "require_ventilator": False, "label": "EMERGENCY bed"},
    ],
    # Level 2: Emergency -> ICU -> General
    2: [
        {"ward": BedWard.EMERGENCY, "require_ventilator": False, "label": "EMERGENCY bed"},
        {"ward": BedWard.ICU, "require_ventilator": False, "label": "ICU bed"},
        {"ward": BedWard.GENERAL, "require_ventilator": False, "label": "GENERAL bed"},
    ],
    # Level 3: Emergency -> General
    3: [
        {"ward": BedWard.EMERGENCY, "require_ventilator": False, "label": "EMERGENCY bed"},
        {"ward": BedWard.GENERAL, "require_ventilator": False, "label": "GENERAL bed"},
    ],
    # Level 4: General only
    4: [
        {"ward": BedWard.GENERAL, "require_ventilator": False, "label": "GENERAL bed"},
    ],
    # Level 5: General only
    5: [
        {"ward": BedWard.GENERAL, "require_ventilator": False, "label": "GENERAL bed"},
    ],
}


def patient_needs_ventilator(patient: Patient) -> bool:
    """
    Check if patient requires mechanical ventilation support:
    SpO2 < 90% or RR > 30/min or symptoms indicate unconsciousness/unresponsiveness.
    """
    if patient.spo2 is not None and patient.spo2 < 90:
        return True
    if patient.rr is not None and patient.rr > 30:
        return True
    if patient.symptoms:
        symptoms_lower = patient.symptoms.lower()
        if "unconscious" in symptoms_lower or "unresponsive" in symptoms_lower:
            return True
    return False


def _has_cardiac_symptoms(patient: Patient) -> bool:
    """Check if symptoms describe acute chest pain or cardiac distress."""
    if not patient.symptoms:
        return False
    text = patient.symptoms.lower()
    return any(term in text for term in ["chest pain", "cardiac", "angina", "heart attack", "myocardial"])


# --- Bed & Doctor Search Helpers ---

def find_best_bed(db: Session, patient: Patient) -> Tuple[Optional[Bed], bool, Optional[str]]:
    """
    Find the most suitable available bed according to patient's urgency level
    and ventilator requirements.

    Returns:
        tuple: (bed: Optional[Bed], is_fallback: bool, fallback_note: Optional[str])
    """
    urgency = patient.urgency_level or 5
    preferences = BED_PREFERENCES.get(urgency, BED_PREFERENCES[5])
    needs_vent = patient_needs_ventilator(patient)

    first_pref_label = preferences[0]["label"]

    for step_idx, pref in enumerate(preferences):
        ward = pref["ward"]
        req_vent = pref["require_ventilator"] or needs_vent

        query = db.query(Bed).filter(
            Bed.ward == ward,
            Bed.status == BedStatus.AVAILABLE,
        )
        if req_vent:
            query = query.filter(Bed.has_ventilator == True)

        bed = query.order_by(Bed.id.asc()).first()
        if bed:
            is_fallback = (step_idx > 0)
            fallback_note = None
            if is_fallback:
                fallback_note = f"Nearest alternative: {bed.ward.value} bed used because {first_pref_label} full"
            return bed, is_fallback, fallback_note

    return None, False, None


def find_best_doctor(db: Session, patient: Patient) -> Optional[Doctor]:
    """
    Find the most suitable on-duty physician based on urgency, clinical specialty,
    and current active patient workload (< MAX_PATIENTS_PER_DOCTOR).
    Among equal specialty matches, chooses lowest active_patients_count.
    """
    urgency = patient.urgency_level or 5
    is_cardiac = _has_cardiac_symptoms(patient)

    # Base candidate pool: available physicians with capacity
    base_query = db.query(Doctor).filter(
        Doctor.is_available == True,
        Doctor.active_patients_count < MAX_PATIENTS_PER_DOCTOR,
    )

    # Define tier ordering of specialties by urgency
    if urgency in (1, 2):
        if is_cardiac:
            tiers = [
                [DoctorSpecialty.CARDIOLOGY],
                [DoctorSpecialty.EMERGENCY],
                [DoctorSpecialty.GENERAL],
            ]
        else:
            tiers = [
                [DoctorSpecialty.EMERGENCY],
                [DoctorSpecialty.CARDIOLOGY, DoctorSpecialty.GENERAL],
            ]
    elif urgency == 3:
        tiers = [
            [DoctorSpecialty.EMERGENCY, DoctorSpecialty.GENERAL],
            [DoctorSpecialty.CARDIOLOGY],
        ]
    else:  # Levels 4 and 5
        tiers = [
            [DoctorSpecialty.GENERAL],
            [DoctorSpecialty.EMERGENCY, DoctorSpecialty.CARDIOLOGY],
        ]

    for tier_specialties in tiers:
        candidate = (
            base_query.filter(Doctor.specialty.in_(tier_specialties))
            .order_by(Doctor.active_patients_count.asc(), Doctor.id.asc())
            .first()
        )
        if candidate:
            return candidate

    return None


# --- Core Allocation Operations ---

def assign_patient(db: Session, patient: Patient) -> Dict:
    """
    Finds a bed and a doctor for the patient.
    If BOTH are found: marks bed OCCUPIED, increments doctor active_patients_count,
    sets patient.assigned_bed_id, assigned_doctor_id, status ASSIGNED, and writes an AuditLog.
    If either is missing: keeps status WAITING, assigns nothing, and writes a Waitlisted AuditLog.

    Returns:
        dict: {"assigned": bool, "bed_id": Optional[str], "doctor_id": Optional[int], "message": str}
    """
    # If patient is already assigned, avoid re-assigning
    if patient.status == PatientStatus.ASSIGNED and patient.assigned_bed_id and patient.assigned_doctor_id:
        return {
            "assigned": True,
            "bed_id": patient.assigned_bed_id,
            "doctor_id": patient.assigned_doctor_id,
            "message": "Patient is already assigned to resources",
        }

    bed, is_fallback, fallback_note = find_best_bed(db, patient)
    doctor = find_best_doctor(db, patient)

    # BOTH resources must be available to avoid partial assignment
    if bed and doctor:
        bed.status = BedStatus.OCCUPIED
        doctor.active_patients_count += 1
        patient.assigned_bed_id = bed.id
        patient.assigned_doctor_id = doctor.id
        patient.status = PatientStatus.ASSIGNED

        # Build assignment log message
        vent_str = ", ventilator" if bed.has_ventilator else ""
        log_event = f"Assigned to {bed.id} ({bed.ward.value}{vent_str}) with {doctor.name}"
        if is_fallback and fallback_note:
            log_event = f"{log_event}. {fallback_note}"

        db.add(AuditLog(patient_id=patient.id, event=log_event, timestamp=datetime.utcnow()))
        db.commit()
        db.refresh(patient)

        return {
            "assigned": True,
            "bed_id": bed.id,
            "doctor_id": doctor.id,
            "message": log_event,
        }

    # If either or both are missing, patient must waitlist
    urgency = patient.urgency_level or 5
    target_ward_label = BED_PREFERENCES.get(urgency, BED_PREFERENCES[5])[0]["label"]

    if not bed and not doctor:
        reason = f"no {target_ward_label} and no doctor available"
    elif not bed:
        reason = f"no {target_ward_label} available"
    else:
        reason = "no doctor available"

    waitlist_msg = f"Waitlisted: {reason}"
    patient.status = PatientStatus.WAITING
    # Ensure no partial assignment exists
    patient.assigned_bed_id = None
    patient.assigned_doctor_id = None

    db.add(AuditLog(patient_id=patient.id, event=waitlist_msg, timestamp=datetime.utcnow()))
    db.commit()
    db.refresh(patient)

    return {
        "assigned": False,
        "bed_id": None,
        "doctor_id": None,
        "message": waitlist_msg,
    }


def release_patient_resources(db: Session, patient: Patient) -> None:
    """
    When a patient is discharged, sets their bed to CLEANING and decrements
    the doctor's patient count (never below 0). Retains historical assignment IDs on patient.
    """
    if patient.assigned_bed_id:
        bed = db.query(Bed).filter(Bed.id == patient.assigned_bed_id).first()
        if bed:
            bed.status = BedStatus.CLEANING

    if patient.assigned_doctor_id:
        doctor = db.query(Doctor).filter(Doctor.id == patient.assigned_doctor_id).first()
        if doctor:
            doctor.active_patients_count = max(0, doctor.active_patients_count - 1)

    db.commit()


def allocate_waiting(db: Session) -> List[int]:
    """
    Iterates through all WAITING patients in priority order (urgency_level asc, created_at asc)
    and calls assign_patient until no more patients can be assigned.
    Returns list of newly assigned patient IDs.
    """
    waiting_patients = (
        db.query(Patient)
        .filter(Patient.status == PatientStatus.WAITING)
        .order_by(Patient.urgency_level.asc(), Patient.created_at.asc())
        .all()
    )

    assigned_patient_ids = []
    for patient in waiting_patients:
        res = assign_patient(db, patient)
        if res["assigned"]:
            assigned_patient_ids.append(patient.id)

    return assigned_patient_ids


def try_upgrade_bed(db: Session, patient: Patient) -> Dict:
    """
    If an ASSIGNED patient's urgency became more severe after re-triage and a more
    suitable bed than their current one is available, transfers them:
    frees old bed (status CLEANING), occupies new bed, and records an AuditLog.
    """
    if patient.status != PatientStatus.ASSIGNED or not patient.assigned_bed_id:
        return {"upgraded": False, "message": "Patient is not currently assigned to a bed"}

    current_bed = db.query(Bed).filter(Bed.id == patient.assigned_bed_id).first()
    if not current_bed:
        return {"upgraded": False, "message": "Current bed record not found"}

    new_bed, is_fallback, _ = find_best_bed(db, patient)
    if not new_bed:
        return {"upgraded": False, "message": "No better bed currently available"}

    # Determine if new_bed is strictly more suitable than current_bed
    urgency = patient.urgency_level or 5
    preferences = BED_PREFERENCES.get(urgency, BED_PREFERENCES[5])

    def get_bed_rank(b: Bed) -> int:
        for idx, pref in enumerate(preferences):
            if b.ward == pref["ward"]:
                if pref["require_ventilator"] and not b.has_ventilator:
                    continue
                return idx
        return 999  # Not in preferences for this urgency

    current_rank = get_bed_rank(current_bed)
    new_rank = get_bed_rank(new_bed)

    # If new bed has lower index (higher preference) or current bed isn't preferred at all
    if new_rank < current_rank:
        old_bed_id = current_bed.id
        current_bed.status = BedStatus.CLEANING
        new_bed.status = BedStatus.OCCUPIED
        patient.assigned_bed_id = new_bed.id

        event_msg = f"Moved from {old_bed_id} to {new_bed.id} after re-prioritization"
        db.add(AuditLog(patient_id=patient.id, event=event_msg, timestamp=datetime.utcnow()))
        db.commit()
        db.refresh(patient)

        return {
            "upgraded": True,
            "old_bed_id": old_bed_id,
            "new_bed_id": new_bed.id,
            "message": event_msg,
        }

    return {"upgraded": False, "message": "Current bed remains optimal or equal to available beds"}
