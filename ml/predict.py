"""
Triage prediction module wrapping the trained XGBoost model.
Exposes predict(patient: dict) -> dict with clinical explainability and safety overrides.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

# --- Model & Artifact Initialization ---
# Load model artifacts once at module import time
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"
MODEL_PATH = MODEL_DIR / "model.json"
FEATURES_PATH = MODEL_DIR / "features.json"

with open(FEATURES_PATH, "r") as f:
    FEATURE_NAMES = json.load(f)

# Load trained XGBoost multiclass model
model = xgb.XGBClassifier()
model.load_model(str(MODEL_PATH))

# Initialize SHAP TreeExplainer for fast feature attribution
explainer = shap.TreeExplainer(model)

# --- Keyword Dictionaries for Symptom Extraction ---
SYMPTOM_KEYWORDS = {
    "chest_pain": [
        "chest pain", "angina", "tightness in chest", "chest pressure",
        "cardiac pain", "chest tightness"
    ],
    "breathlessness": [
        "can't breathe", "cannot breathe", "breathless", "shortness of breath",
        "dyspnea", "breathing difficulty", "trouble breathing", "hard to breathe",
        "gasping", "wheezing"
    ],
    "unconscious": [
        "unconscious", "unresponsive", "passed out", "fainted", "syncope",
        "collapsed", "blacked out", "coma", "loss of consciousness"
    ],
    "severe_bleeding": [
        "severe bleeding", "bleeding", "blood loss", "hemorrhage",
        "hemorrhaging", "profuse bleeding"
    ],
    "fever": [
        "fever", "chills", "high temperature", "pyrexia", "feverish", "shivering"
    ],
    "abdominal_pain": [
        "abdominal pain", "stomach pain", "stomach ache", "belly pain",
        "abdominal cramps", "tummy ache"
    ],
    "headache": [
        "headache", "migraine", "head pain", "throbbing head"
    ],
    "minor_injury": [
        "minor injury", "injury", "cut", "scrape", "sprain", "bruise",
        "fall", "wound", "laceration", "abrasion", "twisted ankle"
    ],
}


def _extract_symptoms(symptoms_text: str) -> dict:
    """Extract binary 0/1 symptom flags from free-text using keyword matching."""
    if not symptoms_text or not isinstance(symptoms_text, str):
        return {k: 0 for k in SYMPTOM_KEYWORDS}
    text_lower = symptoms_text.lower()
    return {
        k: int(any(kw in text_lower for kw in keywords))
        for k, keywords in SYMPTOM_KEYWORDS.items()
    }


def _format_vital_tag(feature: str, val: float) -> str:
    """Convert a feature name and value into plain-English clinical explanation."""
    if feature == "spo2":
        if val < 90:
            return f"SpO2 {int(val)}% (critically low)"
        elif val < 94:
            return f"SpO2 {int(val)}% (low)"
        return f"SpO2 {int(val)}% (normal)"

    elif feature == "hr":
        if val > 140:
            return f"Pulse {int(val)} bpm (critically high)"
        elif val > 120:
            return f"Pulse {int(val)} bpm (very high)"
        elif val > 100:
            return f"Pulse {int(val)} bpm (elevated)"
        elif val < 50:
            return f"Pulse {int(val)} bpm (critically low)"
        elif val < 60:
            return f"Pulse {int(val)} bpm (low)"
        return f"Pulse {int(val)} bpm (normal)"

    elif feature == "sbp":
        if val < 80:
            return f"Systolic BP {int(val)} mmHg (critically low)"
        elif val < 90:
            return f"Systolic BP {int(val)} mmHg (low)"
        elif val > 180:
            return f"Systolic BP {int(val)} mmHg (crisis high)"
        elif val > 140:
            return f"Systolic BP {int(val)} mmHg (high)"
        return f"Systolic BP {int(val)} mmHg (normal)"

    elif feature == "dbp":
        if val < 60:
            return f"Diastolic BP {int(val)} mmHg (low)"
        elif val > 110:
            return f"Diastolic BP {int(val)} mmHg (critically high)"
        elif val > 90:
            return f"Diastolic BP {int(val)} mmHg (high)"
        return f"Diastolic BP {int(val)} mmHg (normal)"

    elif feature == "rr":
        if val > 28:
            return f"Respiratory rate {int(val)}/min (critically high)"
        elif val > 20:
            return f"Respiratory rate {int(val)}/min (rapid)"
        elif val < 10:
            return f"Respiratory rate {int(val)}/min (critically low)"
        return f"Respiratory rate {int(val)}/min (normal)"

    elif feature == "temp":
        if val >= 39.0:
            return f"Temperature {val:.1f}°C (high fever)"
        elif val >= 37.8:
            return f"Temperature {val:.1f}°C (elevated / mild fever)"
        elif val < 35.0:
            return f"Temperature {val:.1f}°C (hypothermia)"
        return f"Temperature {val:.1f}°C (normal)"

    elif feature == "age":
        return f"Age {int(val)} years"

    elif feature == "gender":
        return "Gender: Male" if int(val) == 1 else "Gender: Female"

    # Symptom descriptions
    elif feature == "chest_pain":
        return "Reported chest pain" if val else "No chest pain reported"
    elif feature == "breathlessness":
        return "Reported breathlessness" if val else "No breathlessness reported"
    elif feature == "unconscious":
        return "Patient unconscious / unresponsive" if val else "Alert and responsive"
    elif feature == "severe_bleeding":
        return "Severe bleeding present" if val else "No severe bleeding"
    elif feature == "fever":
        return "Reported fever" if val else "No fever reported"
    elif feature == "abdominal_pain":
        return "Reported abdominal pain" if val else "No abdominal pain reported"
    elif feature == "headache":
        return "Reported headache" if val else "No headache reported"
    elif feature == "minor_injury":
        return "Reported minor injury" if val else "No minor injury reported"

    return f"{feature}: {val}"


def predict(patient: dict) -> dict:
    """
    Predict triage urgency level (1-5) and provide SHAP-based explanatory tags
    with clinical safety rule overrides.

    Parameters:
        patient (dict): Patient demographics, vitals, and symptoms:
            - age (int/float)
            - gender (str: "M" or "F")
            - sbp (int/float): Systolic blood pressure (mmHg)
            - dbp (int/float): Diastolic blood pressure (mmHg)
            - hr (int/float): Heart rate / pulse (bpm)
            - spo2 (int/float): Oxygen saturation (%)
            - temp (float): Temperature (°C)
            - rr (int/float): Respiratory rate (breaths/min)
            - symptoms (str): Free-text symptoms description

    Returns:
        dict: {
            "urgency_level": int (1-5, where 1 = highest urgency, 5 = lowest),
            "reason_tags": [str, ...] (1 to 4 human-readable clinical tags),
            "confidence": float (prediction confidence between 0.0 and 1.0)
        }
    """
    # 1. Map demographic and vital signs with safe type casting
    age = float(patient.get("age", 40))
    gender_raw = str(patient.get("gender", "")).strip().upper()
    gender = 1 if gender_raw in ("M", "MALE", "1") else 0

    sbp = float(patient.get("sbp", 120))
    dbp = float(patient.get("dbp", 80))
    hr = float(patient.get("hr", 75))
    spo2 = float(patient.get("spo2", 98))
    temp = float(patient.get("temp", 37.0))
    rr = float(patient.get("rr", 16))

    # 2. Extract symptom flags from free-text
    symptoms_text = patient.get("symptoms", "")
    symptom_flags = _extract_symptoms(symptoms_text)

    # 3. Assemble feature dictionary and single-row DataFrame in exact order
    feature_row = {
        "age": age,
        "gender": gender,
        "sbp": sbp,
        "dbp": dbp,
        "hr": hr,
        "spo2": spo2,
        "temp": temp,
        "rr": rr,
        **symptom_flags,
    }
    df_row = pd.DataFrame([[feature_row[f] for f in FEATURE_NAMES]], columns=FEATURE_NAMES)

    # 4. Model inference
    probs = model.predict_proba(df_row)[0]
    pred_class = int(model.predict(df_row)[0])  # Classes 0 to 4
    model_urgency = pred_class + 1              # Maps to Urgency Level 1 to 5
    confidence = round(float(probs[pred_class]), 4)

    # 5. SHAP Explanation for predicted class (top 3 features pushing toward this class)
    shap_explanation = explainer(df_row)
    # SHAP shape is (1, n_features, n_classes)
    class_shap_values = shap_explanation.values[0, :, pred_class]

    # Sort feature indices by contribution to predicted class descending
    sorted_indices = np.argsort(class_shap_values)[::-1]

    reason_tags = []
    for idx in sorted_indices:
        feat_name = FEATURE_NAMES[idx]
        val = df_row[feat_name].values[0]
        # Include features pushing toward the class (positive contribution)
        if class_shap_values[idx] > 0 or len(reason_tags) == 0:
            tag = _format_vital_tag(feat_name, val)
            if tag not in reason_tags:
                reason_tags.append(tag)
        if len(reason_tags) == 3:
            break

    # 6. Clinical Safety Override Rules
    # Level 1 Override: immediate life-threatening vitals or unconsciousness
    override_reason = None
    rule_urgency = 5

    if spo2 < 90 or sbp < 80 or hr > 140 or symptom_flags.get("unconscious", 0) == 1:
        rule_urgency = 1
        triggers = []
        if spo2 < 90:
            triggers.append(f"SpO2 {int(spo2)}% < 90%")
        if sbp < 80:
            triggers.append(f"SBP {int(sbp)} < 80 mmHg")
        if hr > 140:
            triggers.append(f"HR {int(hr)} > 140 bpm")
        if symptom_flags.get("unconscious", 0) == 1:
            triggers.append("Unconscious")
        override_reason = f"Safety override: Critical threshold ({', '.join(triggers)}) -> Level 1"

    # Level 2 Override: emergent abnormal vitals (at most level 2)
    elif spo2 < 94 or hr > 120 or rr > 28:
        rule_urgency = 2
        triggers = []
        if spo2 < 94:
            triggers.append(f"SpO2 {int(spo2)}% < 94%")
        if hr > 120:
            triggers.append(f"HR {int(hr)} > 120 bpm")
        if rr > 28:
            triggers.append(f"RR {int(rr)} > 28/min")
        override_reason = f"Safety override: High-risk vitals ({', '.join(triggers)}) -> Level 2"

    # Final urgency is the MORE urgent (smaller number) of model vs safety rules
    final_urgency = min(model_urgency, rule_urgency)

    # If safety rule escalated the urgency, prepend the override reason tag
    if final_urgency < model_urgency and override_reason:
        reason_tags.insert(0, override_reason)

    # 7. Ensure at least 1 tag and at most 4 tags
    if not reason_tags:
        reason_tags.append("Triage evaluation based on vital signs and symptoms")
    reason_tags = reason_tags[:4]

    return {
        "urgency_level": int(final_urgency),
        "reason_tags": reason_tags,
        "confidence": confidence,
    }
