# Hospital Triage ML Service

This directory contains the machine learning triage model and inference pipeline for the hospital triage system. It classifies patients into 5 Emergency Severity Index (ESI) triage levels and produces human-readable, explainable reason tags with clinical safety overrides.

---

## 1. How the Model Was Trained

- **Architecture**: Multiclass gradient boosted decision tree classifier (`xgboost.XGBClassifier`) with 5 classes (0–4 mapping to ESI Urgency Levels 1–5).
- **Training Dataset**: 20,000 synthetic patient records generated in Google Colab (`ml/notebooks/train_triage_model.ipynb`) based on clinical Emergency Severity Index (ESI) algorithms and physiological correlations, with 5% injected label noise to simulate real-world ambiguity.
- **Features (16 total)**:
  - Demographic: `age`, `gender` (0 = F, 1 = M)
  - Vitals: `sbp`, `dbp`, `hr`, `spo2`, `temp`, `rr`
  - Symptoms (binary): `chest_pain`, `breathlessness`, `unconscious`, `severe_bleeding`, `fever`, `abdominal_pain`, `headache`, `minor_injury`
- **Class Imbalance Handling**: Weighted loss via `compute_class_weight('balanced', ...)`.
- **Validation Metrics** (from `ml/model/metrics.json`):
  - Overall Accuracy: ~95.8%
  - Level 1 (Resuscitation) Recall: ~91.9%
  - Level 2 (Emergent) Recall: ~81.9%
  - Mean Critical Recall: ~86.9%

---

## 2. `predict()` Function API

The entrypoint is exposed in `ml/predict.py`:

```python
from predict import predict

patient = {
    "age": 65,
    "gender": "M",  # "M" or "F"
    "sbp": 75,       # Systolic blood pressure (mmHg)
    "dbp": 50,       # Diastolic blood pressure (mmHg)
    "hr": 150,       # Heart rate (bpm)
    "spo2": 85,      # Oxygen saturation (%)
    "temp": 37.2,    # Temperature (°C)
    "rr": 30,        # Respiratory rate (breaths/min)
    "symptoms": "Severe chest pain, cannot breathe, collapsed"
}

result = predict(patient)
```

### Input Format
A dictionary containing:
| Key | Type | Description |
|---|---|---|
| `age` | `int` or `float` | Patient age in years |
| `gender` | `str` | `"M"` / `"F"` (or `"Male"` / `"Female"`) |
| `sbp` | `int` or `float` | Systolic blood pressure (mmHg) |
| `dbp` | `int` or `float` | Diastolic blood pressure (mmHg) |
| `hr` | `int` or `float` | Heart rate / pulse (bpm) |
| `spo2` | `int` or `float` | Blood oxygen saturation percentage |
| `temp` | `float` | Body temperature in °C |
| `rr` | `int` or `float` | Respiratory rate in breaths per minute |
| `symptoms` | `str` | Free-text clinical symptoms (handles empty/missing) |

### Output Format
```json
{
  "urgency_level": 1,
  "reason_tags": [
    "Patient unconscious / unresponsive",
    "SpO2 85% (critically low)",
    "Pulse 150 bpm (critically high)"
  ],
  "confidence": 0.9573
}
```
- `urgency_level` (`int`): 1 (highest urgency / immediate life threat) to 5 (least urgent / non-acute).
- `reason_tags` (`list[str]`): 1 to 4 human-readable clinical explanations generated via SHAP feature attributions and vital sign normal ranges.
- `confidence` (`float`): Model prediction probability (0.0 to 1.0).

### Clinical Safety Override Rules
To safeguard against model under-triaging, deterministic clinical safety rules are enforced after model prediction:
- **Level 1 Override**: If `spo2 < 90` or `sbp < 80` or `hr > 140` or patient is `unconscious`, urgency is enforced to Level 1.
- **Level 2 Override**: If `spo2 < 94` or `hr > 120` or `rr > 28`, urgency is enforced to at most Level 2.
- The final urgency is `min(model_urgency, rule_urgency)`. If a rule escalated urgency, a prominent `"Safety override: ..."` tag is added.

---

## 3. How to Retrain

1. **Open the Notebook**:
   Open `ml/notebooks/train_triage_model.ipynb` in Google Colab or local Jupyter.
2. **Execute Training**:
   Run all cells to regenerate the dataset, train `xgboost.XGBClassifier`, evaluate performance, and compute SHAP explanations.
3. **Export Artifacts**:
   Download the generated `export.zip` and place the extracted files in `ml/model/`:
   - `ml/model/model.json`
   - `ml/model/features.json`
   - `ml/model/metrics.json`
4. **Run Verification**:
   Execute the test suite from the repository root:
   ```bash
   backend/.venv/bin/python ml/test_predict.py
   ```
