# Hospital Triage System

An intelligent emergency-department triage decision-support prototype with ML urgency scoring, SHAP reason tags, resource allocation, live WebSocket updates, and role-based access control.

> **Medical disclaimer:** This is an educational software prototype, not a certified medical device. It has not been validated with real clinical data and must not be used to make real emergency-care decisions. Clinicians remain responsible for all decisions.

## Access policy

Only authorized clinical personnel may sign in:

- `NURSE`
- `DOCTOR`

There is no public registration, no ADMIN sign-in, no built-in demo account, and no default password. User accounts are provisioned from the trusted backend console. ADMIN endpoints and the Admin UI have been removed from the application.

## Quick start (Windows PowerShell)

### 1. Configure the JWT signing secret

Run this once in the PowerShell terminal that will run the backend:

```powershell
$env:TRIAGE_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep this value private. Generate and store a persistent secret securely for deployments; do not commit it to Git. The backend refuses to start without a secret of at least 32 characters.

### 2. Initialize the database and install backend dependencies

```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

If you are upgrading and want to keep your existing account/patient records, back up your old `backend\\triage.db` and copy it into this project's `backend` folder **before** running the next commands. For a fresh installation, do not copy an old database.

```powershell
python seed.py
```

`seed.py` creates the database schema and removes legacy demo login accounts. It does **not** create fictional doctors, nurses, beds, shifts, or patients.

### 3. Migrate an existing demo database (upgrades only)

If you copied an older database from the previous project version, run:

```powershell
python migrate_demo_resources.py
```

This migration:
- Relinks a doctor account to a matching doctor resource record when its display name differs from the old sample doctor.
- Removes only unused known sample doctor and bed records.
- Preserves patient history and any resource still referenced by patient, alert, or staff records.

Back up `backend\\triage.db` before running it. Review the migration output. For a brand-new database, this step is safe to skip.

### 4. Create real staff accounts

```powershell
python create_staff.py
```

Choose `NURSE` or `DOCTOR`. For a doctor, the script creates a matching doctor resource record using the entered full name and selected specialty. It links the login account to that newly created record automatically. There is no need to select an unrelated doctor ID.

Passwords must be at least 12 characters and are stored as password hashes.

### 5. Add real hospital beds

Run once for each actual bed:

```powershell
python create_bed.py
```

Enter the actual bed identifier, ward, and whether it has a ventilator. The application starts with zero beds until actual hospital resources are provisioned.

### 6. Start the backend

```powershell
python -m uvicorn main:app --reload
```

Keep this terminal open.

### 7. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## macOS / Linux

Configure the secret, install dependencies, initialize the database, create staff and beds, then start the backend:

```bash
export TRIAGE_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
python create_staff.py
python create_bed.py
uvicorn main:app --reload
```

In a second terminal, run `cd frontend && npm install && npm run dev`.

## Application features

| Feature | Detail |
|---|---|
| Patient intake | Actual patient demographics, symptoms, and vitals |
| ML triage | XGBoost urgency classification, Levels 1–5 |
| Explainability | SHAP-derived human-readable reason tags |
| Resource allocation | Match waiting patients to configured beds and available doctors |
| Live dashboard | WebSocket updates for queue and resources |
| Alerts | Clinical alerts and escalation notifications |
| Re-prioritization | Re-run triage when patient vitals change |
| Access control | Backend-enforced NURSE and DOCTOR permissions |
| Audit log | Patient-related state changes |
| Analytics | Triage distribution, occupancy, wait times, timeline |

## Project structure

```text
hospital-triage/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── database.py
│   ├── seed.py
│   ├── create_staff.py
│   ├── create_bed.py
│   ├── migrate_demo_resources.py
│   ├── triage_service.py
│   ├── allocation.py
│   ├── alerts.py
│   ├── realtime.py
│   ├── analytics.py
│   └── tests/
├── frontend/
│   └── src/
├── ml/
│   ├── predict.py
│   └── model/
├── tests_e2e/
├── docs/
└── scripts/
```

## Tests

```powershell
# Backend
cd backend
python -m pytest tests/ -v

# Frontend
cd ..\frontend
npm test
npm run build
```

## API documentation

When the backend is running, visit http://127.0.0.1:8000/docs.

## Current limitations

- The ML model was trained on synthetic data and has not been clinically validated.
- Symptom feature extraction includes simple keyword matching.
- SQLite is intended for local development, not concurrent production use.
- No real EHR integration is included.
- This prototype is not suitable for real patient care.
