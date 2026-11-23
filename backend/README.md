# Hospital Triage Backend API & Real-Time Engine

FastAPI core service powering the hospital emergency triage system. Provides clinical intake validation, ML-driven triage evaluation, deterministic resource allocation (beds and physicians), priority queue management, vital re-prioritization, clinical alert service, authenticated real-time WebSocket live updates, Role-Based Access Control (RBAC), and comprehensive audit logging.

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

### Interactive Documentation & OAuth2 Login
In Swagger UI (`/docs`), click the green **Authorize** button in the top right to log in with any seeded account (e.g. `nurse1` / `demo123`). All authenticated requests executed in Swagger will automatically include the `Authorization: Bearer <token>` header.

---

## 2. Authentication & Role-Based Access Control (RBAC)

The system enforces authentication via standard OAuth2 Bearer tokens (`PyJWT`, `HS256`) and passwords securely hashed with `bcrypt`.

### Environment Configuration
- **`TRIAGE_SECRET_KEY`**: Secret key used to sign and verify JWT tokens.
  - *Default in development*: `"dev-secret-key-hospital-triage-change-in-production-only-very-secure"`
  - *Production*: Set `export TRIAGE_SECRET_KEY="<strong-random-secret>"` in your environment.
- **Token Lifetime**: 8 hours.

### Seeded Demo Accounts (Password: `demo123`)
| Username | Role | Display Name | Associated Provider |
|---|---|---|---|
| `admin` | `ADMIN` | System Administrator | None |
| `nurse1` | `NURSE` | Nurse Sarah Jenkins | None |
| `nurse2` | `NURSE` | Nurse David Kim | None |
| `dr1` | `DOCTOR` | Dr. Sarah Chen | Doctor #1 (Emergency) |
| `dr2` | `DOCTOR` | Dr. Marcus Vance | Doctor #2 (Emergency) |
| `dr3` | `DOCTOR` | Dr. Elena Rostova | Doctor #3 (Cardiology) |
| `dr4` | `DOCTOR` | Dr. James Wilson | Doctor #4 (General) |
| `dr5` | `DOCTOR` | Dr. Priya Patel | Doctor #5 (General) |

---

## 3. RBAC Permission Matrix

| Method | Endpoint | Public | NURSE | DOCTOR | ADMIN | Permission Details & Scoping |
|---|---|:---:|:---:|:---:|:---:|---|
| `GET` | `/health` | ✓ | ✓ | ✓ | ✓ | Public system health check |
| `POST` | `/auth/login` | ✓ | ✓ | ✓ | ✓ | Public OAuth2 login (returns Bearer JWT) |
| `GET` | `/auth/me` | | ✓ | ✓ | ✓ | Profile of currently authenticated user |
| `POST` | `/users` | | | | ✓ | Create new user account (Admin only) |
| `GET` | `/users` | | | | ✓ | List all system accounts (Admin only) |
| `PUT` | `/users/{id}/active` | | | | ✓ | Activate or deactivate user (Admin only) |
| `POST` | `/patients` | | ✓ | | ✓ | Emergency intake & triage evaluation |
| `GET` | `/patients` | | ✓ | ✓ | ✓ | View triage patient listing |
| `GET` | `/patients/{id}` | | ✓ | ✓ | ✓ | View single patient clinical details |
| `PUT` | `/patients/{id}/vitals` | | ✓ | ✓ | ✓ | Update vitals & trigger re-prioritization |
| `PUT` | `/patients/{id}/discharge` | | ✓ | ✓ | ✓ | Discharge patient and free resources |
| `GET` | `/patients/{id}/audit` | | ✓ | ✓ | ✓ | View patient audit trail |
| `GET` | `/queue` | | ✓ | ✓ | ✓ | View waiting queue with color & wait time |
| `GET` | `/beds` | | ✓ | ✓ | ✓ | View hospital bed inventory & status |
| `PUT` | `/beds/{id}/status` | | | | ✓ | Update bed status (Admin only) |
| `GET` | `/doctors` | | ✓ | ✓ | ✓ | View on-duty physician rosters |
| `PUT` | `/doctors/{id}/availability`| | | | ✓ | Toggle physician availability (Admin only) |
| `GET` | `/resources/summary` | | ✓ | ✓ | ✓ | Real-time bed, ventilator, & doctor summary |
| `POST` | `/allocate/run` | | | | ✓ | Trigger manual waiting queue allocation |
| `GET` | `/alerts` | | ✓ | ✓* | ✓ | List alerts. *DOCTOR sees only their own |
| `PUT` | `/alerts/{id}/acknowledge` | | ✓ | ✓* | ✓ | Acknowledge alert. *DOCTOR can only ack own |
| `WS` | `/ws?token=<jwt>` | | ✓ | ✓ | ✓ | Authenticated live updates & doctor alerts |

---

## 4. Resource Allocation Rules

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

## 5. Authenticated WebSockets & Clinical Alerts

Live updates and provider alerts are streamed over an authenticated WebSocket connection.

### WebSocket Endpoint: `/ws`
Connect via WebSocket client:
```text
ws://127.0.0.1:8000/ws?token=<jwt>
```
- **Authentication**: Token must be passed in the `token` query parameter. If missing or invalid, the connection is closed with status code `4401`.
- **Role Registration**: Client `role` and `doctor_id` are extracted directly from the verified JWT claims.
- **Keepalive Protocol**: Send `"ping"` to receive `"pong"`. Dead connections are pruned automatically.

### Broadcast Event Types
| Event Type | Description | Key Payload Attributes |
|---|---|---|
| `patient_created` | New patient admitted and triaged | `patient_id`, `urgency_level`, `status` |
| `patient_updated` | Vitals updated or patient re-prioritized | `patient_id`, `urgency_level`, `status`, `level_changed`, `previous_level` |
| `patient_discharged` | Patient discharged, bed moved to `CLEANING` | `patient_id`, `released_bed_id`, `released_doctor_id` |
| `queue_changed` | Waiting queue membership or order altered | None |
| `bed_changed` | Bed status modified or patient assigned | `bed_id` |
| `resources_changed` | Bed, ventilator, or doctor availability updated | None |
| `alert` | High-priority clinical notification | `alert` object, `patient_id`, `doctor_id`, `level`, `message` |

### Clinical Alert Rules
- **Critical Assignment Alert**: Dispatched to the assigned doctor and nurse/admin dashboards:
  ```text
  CRITICAL: <Patient Name> (Level <X>) assigned to <Bed ID>. Reasons: <Reason Tags>
  ```
- **Waitlisted Level 1 Alert**: Dispatched to nurse/admin dashboards when a Level 1 patient cannot be allocated an ICU/Emergency bed:
  ```text
  NO BED: <Patient Name> (Level 1) is waitlisted
  ```
- **Re-prioritization Alert**: Dispatched to assigned doctor and nurse/admin dashboards when acuity worsens:
  ```text
  Re-prioritized: <Patient Name> moved from Level <Old> to Level <New>
  ```
- **Routine Silence**: Routine Level 3–5 admissions do not generate clinical alerts.

### Live Demo WebSocket Client
The client logs in via OAuth2 first, obtains a JWT token, and connects to `/ws?token=<jwt>`:
```bash
cd backend
# Listen as nurse1 (default):
.venv/bin/python ws_client_demo.py

# Listen as a specific physician (Dr. Elena Rostova):
.venv/bin/python ws_client_demo.py -u dr3 -p demo123
```

---

## 6. Running Automated Tests

Run the full pytest suite from inside `backend/`. Tests use an isolated in-memory SQLite database (`StaticPool`), leaving `triage.db` untouched:

```bash
cd backend
.venv/bin/pytest -v
```

All 32 tests verify:
- OAuth2 login flow, password verification, and bad credential rejection
- Token expiration, tampered token rejection, and unauthenticated request blocks (401)
- Role-based permissions matrix across all routes (403 Forbidden enforcement)
- Admin-only user management (creation, listing, deactivation) and password hash hiding
- Doctor alert isolation (doctors cannot view or acknowledge other doctors' alerts)
- WebSocket token authentication (code 4401 rejection for invalid/missing tokens)
- Resource allocation hierarchies, ventilator constraints, and doctor capacity limits
- Acuity sorting, queue wait times, and dynamic bed upgrade triggers

---

## 7. Running the Patient Cohort Simulator

Stream realistic patient cohorts through the API (automatically authenticates as `nurse1`):

```bash
cd backend
.venv/bin/python simulate.py --reset -n 25
```

- `--reset`: Resets `triage.db` (clears alerts, patients, and audit logs; preserves user accounts; resets beds and doctors to `AVAILABLE`).
- `-n / --patients`: Number of patients to stream (default: 25).
- Outputs patient admissions, real-time allocation/waitlist events, and an end-of-run resource summary.
