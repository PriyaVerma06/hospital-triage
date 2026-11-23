"""
Alert service for clinical notifications, physician escalation, and real-time dispatch.
Enforces hospital alert rules and records alerts in the database.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from models import Alert, Patient, PatientStatus
from realtime import publish


def create_alert(
    db: Session,
    patient: Patient,
    doctor_id: Optional[int],
    message: str,
    level: int,
) -> Alert:
    """
    Persist an Alert record in the database and publish a real-time notification
    event to the assigned physician and all connected nurse/admin dashboards.
    """
    alert = Alert(
        patient_id=patient.id,
        doctor_id=doctor_id,
        level=level,
        message=message,
        acknowledged=False,
        created_at=datetime.utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Publish real-time event to the specified doctor and nurse/admin roles
    alert_payload = {
        "type": "alert",
        "alert": {
            "id": alert.id,
            "patient_id": alert.patient_id,
            "doctor_id": alert.doctor_id,
            "level": alert.level,
            "message": alert.message,
            "acknowledged": alert.acknowledged,
            "created_at": alert.created_at.isoformat(),
        },
        "patient_id": patient.id,
        "doctor_id": doctor_id,
        "level": level,
        "message": message,
    }
    publish(alert_payload, doctor_id=doctor_id, roles=["nurse", "admin"])
    return alert


def check_and_alert_assignment(db: Session, patient: Patient):
    """
    Evaluate assignment alert rules:
    - Level 1 or 2 assignment -> CRITICAL alert to assigned doctor & nurses/admins.
    - Level 1 waitlisted without a bed -> NO BED alert to nurses/admins.
    - Level 3-5 assignments create no alert.
    """
    if patient.status == PatientStatus.ASSIGNED and patient.urgency_level in (1, 2):
        reasons = ", ".join(patient.reason_tags) if patient.reason_tags else "Critical vitals"
        bed_id = patient.assigned_bed_id or "unassigned"
        message = f"CRITICAL: {patient.name} (Level {patient.urgency_level}) assigned to {bed_id}. Reasons: {reasons}"
        create_alert(
            db=db,
            patient=patient,
            doctor_id=patient.assigned_doctor_id,
            message=message,
            level=patient.urgency_level,
        )

    elif patient.status == PatientStatus.WAITING and patient.urgency_level == 1:
        message = f"NO BED: {patient.name} (Level 1) is waitlisted"
        create_alert(
            db=db,
            patient=patient,
            doctor_id=None,
            message=message,
            level=1,
        )


def check_and_alert_reprioritization(
    db: Session,
    patient: Patient,
    previous_level: int,
    new_urgency: int,
):
    """
    Evaluate re-prioritization alert rules:
    - Re-prioritized to a more severe level (new_urgency < previous_level) -> alert.
    """
    if new_urgency < previous_level:
        message = f"Re-prioritized: {patient.name} moved from Level {previous_level} to Level {new_urgency}"
        create_alert(
            db=db,
            patient=patient,
            doctor_id=patient.assigned_doctor_id,
            message=message,
            level=new_urgency,
        )
