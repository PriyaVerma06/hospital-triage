"""
Triage service module bridging backend business logic with the ML prediction pipeline.
This is the only module that imports the ml.predict module.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

# Ensure repository root is on sys.path so 'from ml.predict import predict' works
# seamlessly when running from backend/ or subdirectories
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.predict import predict


def run_triage(patient: Any) -> Tuple[int, List[str], float]:
    """
    Execute triage prediction on patient demographic and clinical vitals.

    Parameters:
        patient: A dictionary or object with patient fields (age, gender, sbp,
                 dbp, hr, spo2, temp, rr, symptoms).

    Returns:
        tuple: (urgency_level: int, reason_tags: List[str], confidence: float)
    """
    if isinstance(patient, dict):
        patient_dict = patient
    else:
        # Extract fields from SQLAlchemy model or Pydantic model
        patient_dict = {
            "age": getattr(patient, "age", 40),
            "gender": getattr(patient, "gender", "M"),
            "sbp": getattr(patient, "sbp", 120),
            "dbp": getattr(patient, "dbp", 80),
            "hr": getattr(patient, "hr", 75),
            "spo2": getattr(patient, "spo2", 98.0),
            "temp": getattr(patient, "temp", 37.0),
            "rr": getattr(patient, "rr", 16),
            "symptoms": getattr(patient, "symptoms", "") or "",
        }

    result = predict(patient_dict)
    return (
        int(result["urgency_level"]),
        list(result["reason_tags"]),
        float(result["confidence"]),
    )
