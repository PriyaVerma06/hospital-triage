# TriageOS Frontend

Vite + React + Tailwind CSS v4 frontend for the hospital triage system.
Backend: FastAPI at `http://127.0.0.1:8000`.

---

## Quick start

```bash
npm install          # install deps (includes recharts)
npm run dev          # dev server on :5173, proxies /api and /ws to :8000
npm run build        # production build → dist/
npm test             # Vitest unit tests
```

Demo accounts (password `demo123`): `admin`, `nurse1`, `nurse2`, `dr1`–`dr5`.

---

## Routes & role access

| Route | Allowed roles | Description |
|-------|--------------|-------------|
| `/login` | — | Login page (public) |
| `/intake` | NURSE, ADMIN | New patient intake |
| `/dashboard` | ALL | Live wall monitor |
| `/analytics` | ALL | Charts & KPIs |
| `/history` | ALL (Audit tab: ADMIN, DOCTOR) | Patient list + global audit |
| `/alerts` | ALL | Alert list + acknowledge |
| `/admin` | ADMIN only | Beds/Doctors/Shifts/Users/Logs |
| `/patients/:id` | ALL | Patient detail |

> NURSE is redirected to `/intake` on login; DOCTOR/ADMIN go to `/dashboard`.
> Every role can reach `/dashboard` via the navbar.

---

## Directory structure

```
src/
├── config.js                     API_BASE, wsUrl()
├── main.jsx
├── App.jsx                       Router + AuthProvider + LiveProvider
├── index.css                     Tailwind import + toast/animation CSS

├── context/
│   ├── AuthContext.jsx            token, user, login, logout, hasRole
│   └── LiveContext.jsx            Single WebSocket per tab; subscribe()

├── hooks/
│   ├── useLiveSocket.js           Raw WS — backoff, ping, 4401 logout
│   └── useDashboardData.js        Parallel fetch, debounced refresh, escalation

├── lib/
│   ├── api.js                     All fetch helpers (Bearer auto-attach)
│   ├── urgency.jsx                levelInfo(), <LevelBadge/>
│   ├── validation.js              Form validators (Step 8)
│   ├── dashboardLogic.js          escalation, wait time, bed grouping, filter
│   ├── analyticsLogic.js          formatMinutes, chart data transformers, pageOffset
│   ├── shiftLogic.js              shiftPosition(), formatShiftTime()
│   ├── validation.test.js         47 tests
│   ├── dashboardLogic.test.js     30 tests
│   └── analyticsLogic.test.js     32 tests (incl. shiftLogic)

├── pages/
│   ├── Login.jsx
│   ├── Intake.jsx
│   ├── PatientDetail.jsx
│   ├── Dashboard.jsx              Live dashboard (Step 9)
│   ├── Analytics.jsx              Charts & KPIs (Step 10)
│   ├── History.jsx                Patient list + audit log (Step 10)
│   ├── Alerts.jsx                 Alert list (Step 10)
│   ├── Admin.jsx                  Admin console (Step 10)
│   └── NotFound.jsx

└── components/
    ├── Layout.jsx                 Navbar (all links, alert bell) + AlertToasts
    ├── AlertToasts.jsx            Toast stack + AlertBell icon
    ├── dashboard/
    │   ├── StatusBar.jsx          Connection pill + 5 metric cards
    │   ├── PriorityQueue.jsx      Queue rows, filter, search, escalation ring
    │   ├── ActivePatients.jsx     Assigned table, "my patients" toggle
    │   ├── BedMap.jsx             Ward-grouped bed tiles
    │   ├── DoctorPanel.jsx        Doctor cards with load bars
    │   └── PatientDrawer.jsx      Slide-over: vitals, audit, discharge
    ├── admin/
    │   ├── BedsTab.jsx            Bed CRUD + status control
    │   ├── DoctorsTab.jsx         Doctor CRUD + availability toggle
    │   ├── ShiftsTab.jsx          Day-view timeline + add/delete shifts
    │   ├── UsersTab.jsx           User management + activate/deactivate
    │   └── ActivityLogTab.jsx     Admin action log with load-more
    └── ui/
        ├── Modal.jsx              Accessible dialog overlay
        ├── ConfirmDialog.jsx      Confirm/cancel dialog
        ├── Tabs.jsx               Controlled tab bar
        ├── Pagination.jsx         Prev/Next with page indicator
        ├── EmptyState.jsx         Centred empty state
        ├── ErrorBanner.jsx        Inline error with retry
        ├── Skeleton.jsx           Loading placeholders
        └── StatCard.jsx           KPI metric card
```

---

## Dashboard architecture (Step 9)

### Single-socket design

One WebSocket per browser tab shared between all subscribers:

```
AuthContext (token)
    └── LiveProvider  ←  useLiveSocket (1 WebSocket)
            ├── useDashboardData   subscribe → debounced refetch → escalation
            ├── AlertToasts        subscribe → toast + beep + bell count
            └── Analytics.jsx      subscribe → debounced chart refresh
```

- `useLiveSocket`: exponential back-off (1 s→15 s), 25 s ping, `4401` force-logout.
- Fallback polling every 15 s (dashboard) / 60 s (analytics) when socket is offline.

### Escalation detection

After every refresh, `detectEscalations()` compares previous urgency levels with new ones. Patients whose level number decreased (got worse) are added to `recentlyEscalated` for 8 seconds — shown as a pulsing orange ring and "Escalated" badge.

---

## Analytics (Step 10)

Four recharts panels driven by `/analytics/*`:

| Chart | Endpoint | Library |
|-------|----------|---------|
| Triage Distribution | `/analytics/triage-distribution` | BarChart + Cell |
| Avg Wait by Level | `/analytics/wait-by-level` | BarChart + Cell |
| Bed Occupancy | `/analytics/occupancy` | Horizontal stacked BarChart |
| Arrivals Timeline | `/analytics/timeline` | AreaChart |

Time window selector: **6 h / 24 h / 7 days / 30 days**. Auto-refreshes on `queue_changed` / `resources_changed` socket events (debounced 500 ms) and every 60 s as a fallback.

---

## Admin console (Step 10)

ADMIN-only at `/admin`. Five tabs:

| Tab | CRUD | Key notes |
|-----|------|-----------|
| Beds | Create, edit ward/vent, delete, quick-status | Disabled for OCCUPIED beds; tooltip explains |
| Doctors | Create, edit, delete, availability toggle | PUT returns `warning` on busy→unavailable |
| Shifts | Day-view 24-hour timeline, add, delete | 409 overlap shown inline; Apply Shifts button |
| Users | Create (role + linked doctor), activate toggle | Cannot deactivate yourself |
| Activity Log | List (load more) | 50 entries at a time, newest first |

All destructive actions use `<ConfirmDialog>`. All successes/errors show inline banners.

---

## Shared UI components (`src/components/ui/`)

| Component | Purpose |
|-----------|---------|
| `Modal` | Accessible overlay dialog (Escape to close) |
| `ConfirmDialog` | Confirm/cancel with danger variant |
| `Tabs` | Controlled tab bar with hidden-tab support |
| `Pagination` | Prev/Next with 0-based page |
| `EmptyState` | Emoji + title + message empty state |
| `ErrorBanner` | Red inline error with optional retry |
| `Skeleton` / `SkeletonCard` / `SkeletonTable` | Loading placeholders |
| `StatCard` | KPI value + label + highlight variant |

---

## Tests

```
src/lib/validation.test.js       47 tests  field/form/soft-warning
src/lib/dashboardLogic.test.js   30 tests  escalation, wait-time, bed grouping, filter
src/lib/analyticsLogic.test.js   32 tests  formatMinutes, chart transforms, pageOffset, shiftPosition
─────────────────────────────────────────
Total                           109 tests  all pass
```

Run with: `npm test`

---

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE` | `/api` | Backend base URL (Vite proxy strips prefix) |

---

## Steps completed

| Step | Description |
|------|-------------|
| 8 | Scaffold, Auth, Intake form, PatientDetail |
| 9 | Live dashboard, single WebSocket, alert toasts |
| 10 | Analytics charts, Admin console, History, Alerts, shared UI |
