# Hospital Triage Frontend

React 18 + Vite frontend for the Hospital Triage System.

## Access

Only provisioned NURSE and DOCTOR accounts can sign in. There is no public signup, demo login, or ADMIN dashboard.

## Routes

| Route | Access | Purpose |
|---|---|---|
| `/login` | Public | Clinical staff login |
| `/intake` | NURSE | Enter actual patient details and vitals |
| `/dashboard` | NURSE, DOCTOR | Live queue and resource overview |
| `/patients/:id` | NURSE, DOCTOR | Patient clinical details |
| `/analytics` | NURSE, DOCTOR | Triage and resource analytics |
| `/history` | NURSE, DOCTOR | Patient history and audit trail |
| `/alerts` | NURSE, DOCTOR | Clinical alerts |

The backend enforces all role permissions; frontend route guards are only a usability layer.

## Development

```powershell
npm install
npm run dev
```

The Vite development server runs at http://localhost:5173.

```powershell
npm test
npm run build
```

## Configuration

Set `VITE_API_BASE` only when deploying the frontend against a non-default API path. In local development, Vite proxies `/api` and `/ws` to the FastAPI backend.
