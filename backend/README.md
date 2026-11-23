# Hospital Triage Backend API

FastAPI core service powering the hospital emergency triage system. Provides intake validation, ML-driven triage evaluation, priority queue management, vital updates, and audit logging.

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

## 2. Running Tests

Execute the automated test suite using `pytest` from inside `backend/`. Tests run against an isolated in-memory SQLite database, leaving `triage.db` untouched:

```bash
cd backend
.venv/bin/pytest -v
```

---

## 3. API Endpoints Table

| Method | Endpoint | Description | Request Body | Response Status |
|---|---|---|---|---|
| `GET` | `/health` | Health check endpoint | None | `200 OK` |
| `POST` | `/patients` | Patient intake: validates vitals, executes ML triage, saves record, logs audit event, and places in queue | `PatientCreate` | `201 Created` |
| `GET` | `/patients` | List patients (supports optional `?status=` filter), ordered by urgency ascending (1 first), then wait time | None | `200 OK` |
| `GET` | `/patients/{id}` | Retrieve details of a single patient by ID | None | `200 OK` / `404 Not Found` |
| `PUT` | `/patients/{id}/vitals` | Update vitals, re-evaluate ML triage, update level and tags, record audit re-prioritization event | `VitalsUpdate` | `200 OK` / `404 Not Found` |
| `PUT` | `/patients/{id}/discharge` | Mark patient as `DISCHARGED` and log audit event | None | `200 OK` / `404 Not Found` |
| `GET` | `/patients/{id}/audit` | Retrieve complete audit trail for a patient (newest entries first) | None | `200 OK` / `404 Not Found` |
| `GET` | `/queue` | Priority queue of `WAITING` patients enriched with color (`RED`, `YELLOW`, `GREEN`) and `wait_minutes` | None | `200 OK` |
| `GET` | `/beds` | Read-only listing of hospital bed resources and status | None | `200 OK` |
| `GET` | `/doctors` | Read-only listing of on-duty physicians and availability | None | `200 OK` |

---

## 4. Planned Extensions (Step 4)

Bed and doctor assignment logic will be integrated via hooks marked with `# TODO Step 4` in `main.py`:
- `POST /patients`: Automatic bed allocation (ICU/Emergency/General) and doctor assignment based on specialty and current load.
- `PUT /patients/{id}/vitals`: Dynamic re-evaluation of bed/ward assignment when patient acuity escalates or de-escalates.
- `PUT /patients/{id}/discharge`: Automatic release of bed resource (status `CLEANING` or `AVAILABLE`) and doctor load decrementation.
