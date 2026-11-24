# Presentation Outline – Hospital Triage System (10 Slides)

> Target audience: technical judges / academic panel  
> Suggested duration: 8–12 minutes (1–2 min/slide) + Q&A

---

## Slide 1 — The Problem

**Title:** *"Emergency departments are overwhelmed. Triage is still paper."*

**Bullets:**
- ED wait times routinely exceed 4 hours in busy hospitals
- Paper-based or verbal triage is inconsistent and error-prone
- Missed Level 1 patients (under-triage) can be fatal
- No real-time visibility: charge nurses can't see resource state at a glance

**Suggested screenshot:** A busy ED waiting room (stock photo) alongside a paper triage form.

---

## Slide 2 — The Solution

**Title:** *"An intelligent, real-time triage decision-support system"*

**Bullets:**
- ML-powered urgency scoring (Level 1–5) in under 2 seconds
- Automatic bed and doctor allocation the moment a patient is admitted
- Live WebSocket dashboard: queue, beds, doctors, all synced instantly
- Role-based access: nurses, doctors, and admins each see what they need

**Suggested screenshot:** The live dashboard with the priority queue and bed map visible.

---

## Slide 3 — Architecture

**Title:** *"Full-stack: React + FastAPI + SQLite + XGBoost"*

**Bullets:**
- Frontend: Vite + React + Tailwind CSS, single WebSocket per session
- Backend: FastAPI (async), SQLAlchemy ORM, Uvicorn ASGI
- ML pipeline: XGBoost + SHAP explanations, loaded once at startup
- Data store: SQLite (swap to PostgreSQL for production)

**Suggested screenshot:** The Mermaid architecture diagram from README.md.

> *Mermaid diagram is in the root README – paste the rendered image here.*

---

## Slide 4 — ML Model & Explainability

**Title:** *"XGBoost triage classifier with SHAP reason tags"*

**Bullets:**
- 16 input features: 8 vital signs + 8 symptom keywords
- Trained on synthetic ESI-style labelled data (95.75 % accuracy)
- **Recall Level 1: 91.9 %** | **Recall Level 2: 81.9 %** (see docs/MODEL_CARD.md)
- SHAP values → human-readable reason tags displayed on every patient card

**Suggested screenshot:** Patient detail page showing urgency badge + reason tags (e.g., "Low SpO₂", "Elevated Heart Rate", "Chest Pain").

---

## Slide 5 — Resource Allocation Engine

**Title:** *"Zero-click bed and doctor assignment"*

**Bullets:**
- Priority: ICU beds for Level 1, Emergency for Level 1–2, General for Level 3–5
- Doctors matched by specialty and current patient load (max 3/doctor)
- Waitlist queue automatically drains when a bed or doctor becomes available
- Discharge → bed CLEANING → admin marks AVAILABLE → top-priority patient auto-assigned

**Suggested screenshot:** Bed map panel showing ICU/Emergency/General beds with colour-coded status.

---

## Slide 6 — Live Dashboard

**Title:** *"The whole ED, visible in one screen"*

**Bullets:**
- WebSocket events: patient_created, patient_updated, queue_changed, bed_changed, alert
- Priority queue refreshes without polling; colour-coded RED/YELLOW/GREEN
- Active patients panel; discharge button inline
- DoctorAlertStrip: persistent red banner for unacknowledged alerts

**Suggested screenshot:** Dashboard with priority queue (red item at top) and alert strip visible.

---

## Slide 7 — Alerts & Live Re-Prioritisation

**Title:** *"The system reacts faster than a nurse walking down the hall"*

**Bullets:**
- Admission alert fires for every Level 1 patient (toast + DB record)
- Vitals update re-runs the ML model; if level worsens, escalation alert fires
- Alerts scoped by role: doctors only see their own; nurses/admin see all
- Acknowledge button clears the alert; audit trail records who acknowledged it

**Suggested screenshot:** AlertToasts in the corner of the dashboard + the Alerts page list.

---

## Slide 8 — Security & Audit

**Title:** *"JWT authentication, RBAC, and a full audit trail"*

**Bullets:**
- OAuth2 form login → HS256 JWT (8-hour expiry, signed with TRIAGE_SECRET_KEY)
- Three roles: NURSE, DOCTOR, ADMIN – permission matrix enforced at every endpoint
- Every state change is recorded in the audit log (patient_id, event, timestamp)
- Global audit log visible to ADMIN and DOCTOR; per-patient audit available to all roles

**Suggested screenshot:** Admin → Activity Log tab showing a list of audit entries with timestamps.

---

## Slide 9 — Results & Metrics

**Title:** *"What we built and what it delivers"*

**Bullets:**
- **95.75 %** overall ML accuracy on held-out synthetic test data
- **91.9 %** recall on Level 1 (critical) patients
- Backend: 50+ API endpoints, 109 frontend unit tests, 100 % pytest suite pass
- End-to-end smoke test covers all critical paths in a single script

**Suggested screenshot:** `npm test` output showing 109/109 passed; `pytest` summary.

---

## Slide 10 — Future Work

**Title:** *"What comes next"*

**Bullets:**
- **Real EHR integration** – HL7 FHIR ingest from hospital systems
- **Real training data** – IRB-approved dataset, rigorous clinical validation
- **PostgreSQL + Docker** – production-grade persistence and containerisation
- **SMS/pager alerts** – Twilio integration for off-screen doctor notification
- **Audit export** – CSV/PDF download for regulatory compliance

**Suggested screenshot:** System architecture diagram annotated with the "next steps" components.

---

## 8 Likely Judge Questions & Short Answers

| # | Question | Short Answer |
|---|----------|--------------|
| 1 | **Why XGBoost and not a neural network?** | XGBoost is interpretable, trains fast on tabular data, and SHAP explanations work directly on tree models. For this problem size a neural net offers no accuracy advantage but adds opacity and latency. |
| 2 | **Why synthetic training data?** | Real ED data requires IRB approval, de-identification, and institutional access. Synthetic data lets us demonstrate the full ML pipeline cleanly; we document this limitation prominently in the model card. |
| 3 | **How do you avoid under-triage (missing a Level 1)?** | Safety-override rules hard-force Level 1 when SpO₂ < 85%, HR < 40 or > 150, SBP < 75, or RR < 8 or > 30 — regardless of model output. Level 1 recall is also prioritised during training (91.9%). |
| 4 | **How does re-prioritisation work?** | Any vitals update re-runs the full ML pipeline. If the urgency level worsens, an escalation alert is dispatched, the queue resort happens immediately, and the system tries to find a higher-acuity bed. |
| 5 | **How is it secured?** | HS256 JWT tokens with 8-hour expiry. Every protected endpoint uses a FastAPI dependency that decodes the token and checks the user's role against an allow-list. Doctors are further scoped to their own patients/alerts. |
| 6 | **How would it scale?** | Replace SQLite with PostgreSQL, add Redis for WebSocket pub/sub across multiple workers, deploy with Docker Compose or Kubernetes. The FastAPI async architecture supports horizontal scaling. |
| 7 | **What about false alarms?** | The model can over-triage (flag Level 2 when Level 3 is correct), which is the safer direction. Clinicians always make the final call; the system is advisory. Alert fatigue is mitigated by scoping alerts to the responsible doctor. |
| 8 | **What is the role of the doctor?** | Doctors receive alerts and acknowledge them. They can update vitals, discharge patients, and view the full dashboard. The system assists — it never autonomously makes clinical decisions. |
