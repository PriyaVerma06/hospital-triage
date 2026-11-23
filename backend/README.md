# Hospital Triage Backend API & Resource Allocation Engine

FastAPI core service powering the hospital emergency triage system. Provides clinical intake validation, ML-driven triage evaluation, deterministic resource allocation (beds and physicians), priority queue management, vital re-prioritization, and audit logging.

---

## 1. Running the Server

Activate the virtual environment and launch Uvicorn with auto-reload from inside `backend/`:

```bash
cd backend
.venv/bin/uvicorn main:app --reload
```

- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive OpenAPI (Swagger) Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## 2. Resource Allocation Rules

The resource matching engine (`backend/allocation.py`) matches admitted patients to hospital beds and available physicians:

### Bed Preference Hierarchy (First available match wins)
| Urgency Level | Preferred Bed Order | Notes |
|---|---|---|
| **Level 1 (Resuscitation)** | ICU (ventilator) &rarr; ICU &rarr; EMERGENCY | Fallback to EMERGENCY only if ICU is full |
| **Level 2 (Emergent)** | EMERGENCY &rarr; ICU &rarr; GENERAL | Fallback to ICU or GENERAL if EMERGENCY is full |
| **Level 3 (Urgent)** | EMERGENCY &rarr; GENERAL | May utilize Emergency or General beds |
| **Level 4 (Less Urgent)** | GENERAL only | Never assigned ICU or Emergency beds |
| **Level 5 (Non-Urgent)** | GENERAL only | Never assigned ICU or Emergency beds |

- **Ventilator Rule**: If a patient requires mechanical ventilation (`SpO2 < 90%`, `RR > 30/min`, or symptoms indicating unconsciousness/unresponsiveness), only beds with `has_ventilator=True` (ICU beds) are eligible.
- **Bed Upgrades**: If an assigned patient's acuity worsens upon vitals update (e.g. Level 4 &rarr; Level 1), the engine automatically transfers them to a higher-tier bed (e.g. ICU), setting the previous bed to `CLEANING`.

### Physician Selection Rules
- **Capacity Constraint**: `MAX_PATIENTS_PER_DOCTOR = 5`. Doctors with 5 active patients are skipped.
- **Specialty Preference**:
  - **Level 1–2**: Cardiology if symptoms mention chest pain/cardiac terms; otherwise Emergency, then any available doctor.
  - **Level 3**: Emergency or General, then any available doctor.
  - **Level 4–5**: General, then any available doctor.
- **Tie-Breaking**: Among matching specialty tiers, the physician with the lowest `active_patients_count` is selected.

---

## 3. Running Automated Tests

Run the full pytest suite from inside `backend/`. Tests use an isolated in-memory SQLite database, leaving `triage.db` untouched:

```bash
cd backend
.venv/bin/pytest -v
```

---

## 4. Running the Patient Cohort Simulator

A realistic patient simulator is provided in `simulate.py` to stream patient cohorts through the API:

```bash
cd backend
.venv/bin/python simulate.py --reset -n 25
```

- `--reset`: Resets `triage.db` (clears patients and audit logs, sets all beds and doctors back to `AVAILABLE`).
- `-n / --patients`: Number of patients to stream (default: 25).
- Outputs patient admissions, real-time allocation/waitlist events, and an end-of-run resource summary.

---

## 5. API Endpoints Reference

| Method | Endpoint | Description | Request Body | Response Status |
|---|---|---|---|---|
| `GET` | `/health` | Health check endpoint | None | `200 OK` |
| `POST` | `/patients` | Patient intake: runs ML triage, allocates bed and doctor, logs audit trail | `PatientCreate` | `201 Created` |
| `GET` | `/patients` | List patients (supports optional `?status=` filter), ordered by urgency (1 first), then wait time | None | `200 OK` |
| `GET` | `/patients/{id}` | Retrieve details of a single patient by ID | None | `200 OK` / `404 Not Found` |
| `PUT` | `/patients/{id}/vitals` | Update vitals, re-evaluate ML triage, upgrade bed if acuity worsened, log audit event | `VitalsUpdate` | `200 OK` / `404 Not Found` |
| `PUT` | `/patients/{id}/discharge` | Mark patient as `DISCHARGED`, set bed to `CLEANING`, decrement doctor workload, and trigger allocation for waiting queue | None | `200 OK` / `404 Not Found` |
| `GET` | `/patients/{id}/audit` | Retrieve complete chronological audit trail for a patient (newest entries first) | None | `200 OK` / `404 Not Found` |
| `GET` | `/queue` | Priority queue of `WAITING` patients enriched with color (`RED`, `YELLOW`, `GREEN`) and `wait_minutes` | None | `200 OK` |
| `GET` | `/beds` | Read-only listing of hospital bed resources and status | None | `200 OK` |
| `PUT` | `/beds/{id}/status` | Update bed status (`AVAILABLE`, `OCCUPIED`, `CLEANING`). Setting to `AVAILABLE` triggers allocation of waiting queue | `BedStatusUpdate` | `200 OK` / `404 Not Found` |
| `GET` | `/doctors` | Read-only listing of on-duty physicians and availability | None | `200 OK` |
| `PUT` | `/doctors/{id}/availability` | Toggle doctor availability (`is_available`). Setting to `True` triggers allocation of waiting queue | `DoctorAvailabilityUpdate` | `200 OK` / `404 Not Found` |
| `GET` | `/resources/summary` | Real-time breakdown of bed occupancy per ward, free ventilators, available doctors, and waiting queue length | None | `200 OK` |
| `POST` | `/allocate/run` | Manually run allocation engine over waiting queue | None | `200 OK` |

---

## 6. Planned Extensions (Step 5)
Provider notifications and alerting hooks will be integrated via placeholders marked `# TODO Step 5: send alert to assigned doctor`:
- Real-time notification dispatch when a physician is assigned to a high-acuity patient.
- Escalation alerts when a patient is re-prioritized or moved between wards.
