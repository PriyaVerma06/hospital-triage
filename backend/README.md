# Hospital Triage Backend

FastAPI service for patient intake, ML triage, resource allocation, alerts, analytics, audit history, and authenticated WebSocket updates.

## Authentication policy

Only provisioned `NURSE` and `DOCTOR` accounts can sign in. There is no public signup endpoint, no HTTP user-management endpoint, and no ADMIN sign-in. Accounts are created offline from the trusted server console:

```powershell
python create_staff.py
```

For a DOCTOR account, this creates a matching `doctors` row and links it to the user account. For a NURSE account, no doctor row is created.

`TRIAGE_SECRET_KEY` must be set in the environment to a unique random string of at least 32 characters. There is no built-in fallback.

## Dynamic hospital resources

The database starts without fictional hospital beds or doctor records. Add each actual bed with:

```powershell
python create_bed.py
```

Doctor resource records are created automatically with DOCTOR staff accounts. To upgrade an older demo database, back it up and run:

```powershell
python migrate_demo_resources.py
```

The migration preserves patient history and resources that still have clinical references.

## Start the API

```powershell
python -m uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Main endpoints

| Method | Path | Access |
|---|---|---|
| GET | `/health` | Public |
| POST | `/auth/login` | Public login for provisioned clinical staff |
| GET | `/auth/me` | NURSE, DOCTOR |
| POST | `/patients` | NURSE |
| GET | `/patients` | NURSE, DOCTOR |
| GET | `/patients/{id}` | NURSE, DOCTOR |
| PUT | `/patients/{id}/vitals` | NURSE, DOCTOR |
| PUT | `/patients/{id}/discharge` | NURSE, DOCTOR |
| GET | `/queue` | NURSE, DOCTOR |
| GET | `/beds` | NURSE, DOCTOR |
| PUT | `/beds/{id}/status` | NURSE |
| GET | `/doctors` | NURSE, DOCTOR |
| PUT | `/doctors/{id}/availability` | NURSE |
| GET | `/alerts` | NURSE, DOCTOR |
| PUT | `/alerts/{id}/acknowledge` | NURSE, assigned DOCTOR |
| GET | `/analytics/*` | NURSE, DOCTOR |
| GET | `/audit` | NURSE, DOCTOR |
| WS | `/ws?token=<jwt>` | NURSE, DOCTOR |

All protected routes enforce permissions in the backend. Hiding a frontend page is not treated as an authorization control.

## Tests

```powershell
python -m pytest tests/ -v
```

The tests use isolated synthetic fixtures; these do not create demo accounts or sample hospital resources in the real application database.
