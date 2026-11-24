# Demo Script – Hospital Triage System (5 Minutes)

> **Built around `python demo.py scenario` and the live frontend at http://localhost:5173**

---

## Pre-Demo Checklist (do this 5 minutes before presenting)

- [ ] Terminal 1 open in `backend/` with the FastAPI server running
- [ ] Terminal 2 open in `frontend/` with the Vite dev server running (or use `scripts/start.sh`)
- [ ] Chrome open at **http://localhost:5173**
- [ ] Two browser tabs or windows ready: one for `nurse1`, one for `admin`
- [ ] Database reset: `cd backend && python demo.py reset`
- [ ] Confirm health: `curl http://localhost:8000/health` → `{"status":"ok","db":"ok","model_loaded":true}`

---

## Demo Accounts

| Login | Password | Role |
|-------|----------|------|
| `nurse1` | demo123 | NURSE – admits patients, sees queue |
| `dr1` | demo123 | DOCTOR – sees own alerts, dashboard |
| `admin` | demo123 | ADMIN – full access, analytics, admin panel |

---

## The Story (5 minutes, 6 beats)

### 🎬 Beat 1 — Digital Intake (60 s)

**Window 1 → logged in as `nurse1`**

> *"A patient walks in. The nurse opens the intake form – no paper, no phone call."*

1. Click **+ New Patient** in the navbar.
2. Fill in:
   - Name: **Emily Parker**, Age: 34, Gender: F
   - Symptoms: `Minor ankle sprain after twisting foot`
   - Vitals: SBP 118 / DBP 76 / HR 72 / SpO₂ 99 / Temp 36.6 / RR 14
3. Click **Submit**.
4. Point to: **Level 4** (green badge), reason tags `Minor Injury`, auto-assigned or in queue.

> *"In under two seconds, the ML model scores this patient Level 4. The tags tell the nurse exactly why."*

---

### 🎬 Beat 2 — Critical Patient + Auto-Allocation (60 s)

> *"Now a trauma comes in – unconscious, chest pain, SpO₂ at 83%."*

1. Still as `nurse1`, create a second patient:
   - Name: **Margaret Chen**, Age: 72, Gender: F
   - Symptoms: `Severe crushing chest pain, unresponsive, gasping for air`
   - SBP 70 / DBP 44 / HR 38 / SpO₂ 83 / Temp 35.0 / RR 7
2. Submit → show **Level 1** (red badge), ICU bed assigned, doctor assigned.
3. Switch to the **Dashboard** tab → highlight the red entry at the top of the Priority Queue.

> *"Level 1. The system immediately assigns an ICU bed with a ventilator and the most available specialist. No human had to look up which beds were free."*

---

### 🎬 Beat 3 — ICU Full → Alert Toast (45 s)

**Run in terminal:**
```bash
cd backend && python demo.py scenario --speed fast
```

> *"I'll now run a scripted scenario that fills the ICU and creates a waiting critical patient."*

- Point at the terminal narration (scenes B and C).
- Switch to the browser → Dashboard → show the **alert toast** appearing in the corner.
- Show the **queue** – the Level 1 patient is at the top in red, waitlisted.

> *"When ICU fills up, the system still flags the patient as critical and queues them for the first available bed – live, in real time."*

---

### 🎬 Beat 4 — Re-Prioritisation (45 s)

> *"Back to Emily Parker. Her condition has just deteriorated dramatically."*

1. As `nurse1`, go to **History** → find Emily Parker → click her name.
2. Click **Update Vitals**.
3. Enter: SBP 68 / DBP 42 / HR 148 / SpO₂ 81 / Temp 39.9 / RR 36.
4. Submit → show the badge flip from **Level 4 → Level 1**.
5. Switch to the Dashboard → Emily has jumped to the top of the queue.

> *"The model re-runs instantly. Emily goes from Level 4 to Level 1. An escalation alert fires to the doctor. The queue re-sorts itself – no manual intervention."*

---

### 🎬 Beat 5 — Discharge + Bed Auto-Assignment (45 s)

> *"An ICU patient is ready to go home. The nurse discharges them."*

1. As `nurse1`, discharge the first admitted critical patient (from History or PatientDetail).
2. As `admin`, go to **Admin → Beds** → find the CLEANING bed → set it to **AVAILABLE**.
3. Watch the queue: the top waiting patient auto-assigns to that freed bed.

> *"The bed lifecycle is tracked: Occupied → Cleaning → Available. The moment it's available, the allocation engine runs and the top-priority waiting patient is assigned – automatically."*

---

### 🎬 Beat 6 — Analytics + Admin (45 s)

**Window 2 → logged in as `admin`**

> *"The charge nurse and administrator get a live analytics view."*

1. Click **Analytics** – show the 4 charts: triage distribution, occupancy, wait times by level, timeline.
2. Change the time window to **7 days** – charts refresh.
3. Click **Admin → Beds** – show the bed manager.
4. Click **Admin → Activity Log** – show who did what.

> *"Full audit trail, role-based access, live charts. A nurse trying to access the Admin panel gets a 403 – we enforce RBAC at the API level."*

---

## If Something Breaks

| Problem | Fix |
|---------|-----|
| Backend 500 or no response | `cd backend && python demo.py reset && uvicorn main:app --reload` |
| Frontend blank / crash | `cd frontend && npm run dev` |
| Login fails | Run `python demo.py reset` to reseed users |
| Charts empty | Run `python demo.py scenario --speed fast` to populate data |
| WebSocket not connecting | Reload the page; Vite proxy auto-reconnects |
| "No bed available" for critical | Expected! That's scene C of the demo |

---

## Two-Window Setup (Recommended)

| Window | Login | Purpose |
|--------|-------|---------|
| Left (main) | `nurse1` | Intake, queue, history, alerts |
| Right (secondary) | `admin` | Analytics, admin panel, discharge management |

Open as separate Chrome windows (not tabs) for side-by-side comparison.
