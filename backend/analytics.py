"""
Analytics API for the hospital triage system.
Provides aggregated metrics for administrative dashboards and clinical overviews.
All endpoints require ADMIN, DOCTOR, or NURSE role.
All endpoints accept ?hours=N (default 24, max 720) to scope the time window.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Bed, BedStatus, BedWard, Doctor, Patient, PatientStatus, User, UserRole

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Map urgency level → human-readable label and triage color
URGENCY_LABELS = {1: "Immediate", 2: "Emergent", 3: "Urgent", 4: "Less Urgent", 5: "Non-Urgent"}
URGENCY_COLORS = {1: "RED", 2: "RED", 3: "YELLOW", 4: "GREEN", 5: "GREEN"}


def _resolve_window(hours: int) -> datetime:
    """Return the UTC datetime representing the start of the analytics window."""
    return datetime.utcnow() - timedelta(hours=min(hours, 720))


def _safe_div(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or 0.0 if denominator is zero."""
    return round(numerator / denominator, 2) if denominator else 0.0


# ---------------------------------------------------------------------------
# GET /analytics/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_summary(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    High-level operational summary for the given time window:
    - total patients admitted, assigned, waiting, discharged
    - average triage urgency level
    - average wait time (time from admission to first assignment, in minutes)
    - escalation rate (patients that became Level 1 or 2)
    """
    since = _resolve_window(hours)
    patients = db.query(Patient).filter(Patient.created_at >= since).all()

    total = len(patients)
    if total == 0:
        return {
            "hours": hours,
            "total_patients": 0,
            "assigned": 0,
            "waiting": 0,
            "discharged": 0,
            "avg_urgency_level": 0.0,
            "avg_wait_minutes": 0.0,
            "critical_count": 0,
            "escalation_rate_pct": 0.0,
        }

    assigned = sum(1 for p in patients if p.status == PatientStatus.ASSIGNED)
    waiting = sum(1 for p in patients if p.status == PatientStatus.WAITING)
    discharged = sum(1 for p in patients if p.status == PatientStatus.DISCHARGED)
    critical = sum(1 for p in patients if p.urgency_level in (1, 2))

    # Average urgency level (only patients that have been triaged)
    triaged = [p for p in patients if p.urgency_level is not None]
    avg_urgency = _safe_div(sum(p.urgency_level for p in triaged), len(triaged))

    # Wait time: for ASSIGNED/DISCHARGED use assigned_at - created_at;
    # for WAITING use now - created_at.
    now = datetime.utcnow()
    wait_minutes_list = []
    for p in patients:
        if p.status == PatientStatus.WAITING:
            wait_minutes_list.append((now - p.created_at).total_seconds() / 60.0)
        elif p.assigned_at:
            wait_minutes_list.append((p.assigned_at - p.created_at).total_seconds() / 60.0)

    avg_wait = _safe_div(sum(wait_minutes_list), len(wait_minutes_list))

    return {
        "hours": hours,
        "total_patients": total,
        "assigned": assigned,
        "waiting": waiting,
        "discharged": discharged,
        "avg_urgency_level": avg_urgency,
        "avg_wait_minutes": round(avg_wait, 2),
        "critical_count": critical,
        "escalation_rate_pct": round(critical / total * 100, 1),
    }


# ---------------------------------------------------------------------------
# GET /analytics/triage-distribution
# ---------------------------------------------------------------------------

@router.get("/triage-distribution")
def get_triage_distribution(
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Count patients by urgency level 1-5 within the time window.
    Always returns all 5 levels (count=0 for absent levels).
    """
    since = _resolve_window(hours)
    patients = db.query(Patient).filter(Patient.created_at >= since).all()

    counts = {lvl: 0 for lvl in range(1, 6)}
    for p in patients:
        if p.urgency_level in counts:
            counts[p.urgency_level] += 1

    distribution = [
        {
            "level": lvl,
            "label": URGENCY_LABELS[lvl],
            "color": URGENCY_COLORS[lvl],
            "count": counts[lvl],
        }
        for lvl in range(1, 6)
    ]

    return {"hours": hours, "distribution": distribution}


# ---------------------------------------------------------------------------
# GET /analytics/occupancy
# ---------------------------------------------------------------------------

@router.get("/occupancy")
def get_occupancy(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Current real-time bed occupancy grouped by ward.
    Reports AVAILABLE / OCCUPIED / CLEANING counts and ventilator stats.
    No time-window filter (beds are a live resource, not a time-series).
    """
    all_beds = db.query(Bed).all()

    wards = [BedWard.ICU, BedWard.EMERGENCY, BedWard.GENERAL]
    wards_data = {}

    for ward in wards:
        ward_beds = [b for b in all_beds if b.ward == ward]
        total = len(ward_beds)
        available = sum(1 for b in ward_beds if b.status == BedStatus.AVAILABLE)
        occupied = sum(1 for b in ward_beds if b.status == BedStatus.OCCUPIED)
        cleaning = sum(1 for b in ward_beds if b.status == BedStatus.CLEANING)
        wards_data[ward.value] = {
            "total": total,
            "available": available,
            "occupied": occupied,
            "cleaning": cleaning,
            "occupancy_pct": _safe_div(occupied * 100.0, total),
        }

    # Ventilator stats (across all wards)
    total_vents = sum(1 for b in all_beds if b.has_ventilator)
    free_vents = sum(1 for b in all_beds if b.has_ventilator and b.status == BedStatus.AVAILABLE)

    return {
        "wards": wards_data,
        "ventilators": {
            "total": total_vents,
            "free": free_vents,
            "in_use": total_vents - free_vents,
        },
        "total_beds": len(all_beds),
    }


# ---------------------------------------------------------------------------
# GET /analytics/wait-by-level
# ---------------------------------------------------------------------------

@router.get("/wait-by-level")
def get_wait_by_level(
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Average wait time (in minutes) grouped by urgency level for the time window.
    For WAITING patients uses now - created_at; for others uses assigned_at - created_at.
    Returns all 5 levels (avg_wait_minutes=0.0 for levels with no data).
    """
    since = _resolve_window(hours)
    patients = db.query(Patient).filter(Patient.created_at >= since).all()

    now = datetime.utcnow()
    wait_by_level: Dict[int, List[float]] = {lvl: [] for lvl in range(1, 6)}

    for p in patients:
        if p.urgency_level is None or p.urgency_level not in wait_by_level:
            continue
        if p.status == PatientStatus.WAITING:
            wait_by_level[p.urgency_level].append((now - p.created_at).total_seconds() / 60.0)
        elif p.assigned_at:
            wait_by_level[p.urgency_level].append((p.assigned_at - p.created_at).total_seconds() / 60.0)

    result = [
        {
            "level": lvl,
            "label": URGENCY_LABELS[lvl],
            "avg_wait_minutes": round(_safe_div(sum(times), len(times)), 2),
            "patient_count": len(times),
        }
        for lvl, times in wait_by_level.items()
    ]

    return {"hours": hours, "wait_by_level": result}


# ---------------------------------------------------------------------------
# GET /analytics/timeline
# ---------------------------------------------------------------------------

@router.get("/timeline")
def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Hourly admission timeline for the given window.
    Returns one entry per hour (even if 0 patients) with:
      - arrivals: total patients admitted in that hour
      - critical: patients with urgency_level in {1, 2} admitted in that hour
    Hour labels are formatted as 'YYYY-MM-DDTHH:00' in UTC.
    """
    since = _resolve_window(hours)
    patients = db.query(Patient).filter(Patient.created_at >= since).all()

    # Build a dict keyed by truncated hour
    hour_arrivals: Dict[str, int] = {}
    hour_critical: Dict[str, int] = {}

    # Pre-populate all hours in the window (oldest first)
    now = datetime.utcnow()
    # Truncate to the hour
    start_hour = since.replace(minute=0, second=0, microsecond=0)
    current_hour = start_hour
    while current_hour <= now:
        label = current_hour.strftime("%Y-%m-%dT%H:00")
        hour_arrivals[label] = 0
        hour_critical[label] = 0
        current_hour += timedelta(hours=1)

    for p in patients:
        label = p.created_at.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")
        if label in hour_arrivals:
            hour_arrivals[label] += 1
            if p.urgency_level in (1, 2):
                hour_critical[label] += 1

    timeline = [
        {"hour": h, "arrivals": hour_arrivals[h], "critical": hour_critical[h]}
        for h in sorted(hour_arrivals.keys())
    ]

    return {"hours": hours, "timeline": timeline}
