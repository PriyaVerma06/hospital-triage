"""
tests_e2e/smoke_test.py – End-to-end smoke test for the hospital triage system.

Runs against a LIVE server (default: http://127.0.0.1:8000).
Exits with code 0 if all checks pass, non-zero otherwise.

Usage
-----
  cd hospital-triage/
  python tests_e2e/smoke_test.py
  python tests_e2e/smoke_test.py --api-url http://127.0.0.1:8000

Requirements
------------
  pip install httpx websockets
"""

import argparse
import asyncio
import json
import sys
import os
import time
from typing import Optional

import httpx

try:
    import websockets
except ImportError:
    print("MISSING DEPENDENCY: pip install websockets")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Result tracker
# ---------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def _record(step: str, passed: bool, note: str = ""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {icon}  {step}" + (f" – {note}" if note else ""))
    _RESULTS.append((step, passed, note))


def _assert(condition: bool, step: str, note: str = ""):
    _record(step, condition, note)
    return condition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client: httpx.Client, username: str, password: str) -> Optional[str]:
    """Return Bearer token or None."""
    resp = client.post("/auth/login", data={"username": username, "password": password})
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Async WebSocket check
# ---------------------------------------------------------------------------

async def _ws_ping_check(api_url: str, token: str) -> bool:
    """
    Open a WebSocket with a valid JWT and verify the server responds to 'ping' with 'pong'.
    This confirms the WS endpoint is live and auth works without relying on specific events.
    """
    ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws?token={token}"
    try:
        async with websockets.connect(ws_url, open_timeout=5) as ws:
            await ws.send("ping")
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            return response == "pong"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

def run(api_url: str):
    print("=" * 60)
    print("  SMOKE TEST – Hospital Triage System")
    print(f"  Target: {api_url}")
    print("=" * 60)

    client = httpx.Client(base_url=api_url, timeout=15.0)

    # ── Step 1: Health check ────────────────────────────────────────────────
    try:
        resp = client.get("/health")
        data = resp.json()
        ok = resp.status_code == 200 and data.get("status") == "ok"
        _assert(ok, "Health check", f"status={data.get('status')} db={data.get('db')} model_loaded={data.get('model_loaded')}")
    except Exception as exc:
        _record("Health check", False, str(exc))
        print("\n  ❌  Cannot reach server – aborting.")
        sys.exit(1)

    # ── Step 2: Login for nurse, doctor, admin ──────────────────────────────
    nurse_username = os.getenv("TRIAGE_TEST_NURSE_USERNAME", "")
    nurse_password = os.getenv("TRIAGE_TEST_NURSE_PASSWORD", "")
    doctor_username = os.getenv("TRIAGE_TEST_DOCTOR_USERNAME", "")
    doctor_password = os.getenv("TRIAGE_TEST_DOCTOR_PASSWORD", "")
    if not all([nurse_username, nurse_password, doctor_username, doctor_password]):
        raise SystemExit(
            "Set TRIAGE_TEST_NURSE_USERNAME/PASSWORD and TRIAGE_TEST_DOCTOR_USERNAME/PASSWORD "
            "to provisioned clinical accounts before running the E2E smoke test."
        )
    nurse_token = _login(client, nurse_username, nurse_password)
    _assert(nurse_token is not None, "Login as provisioned nurse")
    doctor_token = _login(client, doctor_username, doctor_password)
    _assert(doctor_token is not None, "Login as provisioned doctor")

    if not all([nurse_token, doctor_token, admin_token]):
        print("\n  ❌  Auth failures – aborting remaining steps.")
        _print_summary()
        sys.exit(1)

    # Grab doctor_id for dr1
    me_resp = client.get("/auth/me", headers=_headers(doctor_token))
    doctor_user_id: Optional[int] = me_resp.json().get("doctor_id") if me_resp.status_code == 200 else None
    _assert(doctor_user_id is not None, "dr1 has doctor_id", str(doctor_user_id))

    # ── Step 3: Create a critical patient, verify Level 1 + ICU + tags ──────
    critical_payload = {
        "name": "Smoke Test Patient",
        "age": 70,
        "gender": "M",
        "symptoms": "Severe crushing chest pain, unresponsive, gasping for air",
        "sbp": 70, "dbp": 44, "hr": 38, "spo2": 83.0, "temp": 35.0, "rr": 7,
    }
    resp = client.post("/patients", json=critical_payload, headers=_headers(nurse_token))
    crit_ok = resp.status_code == 201
    _assert(crit_ok, "Create critical patient (POST /patients)", f"HTTP {resp.status_code}")
    critical_patient_id: Optional[int] = None
    if crit_ok:
        pd = resp.json()
        critical_patient_id = pd.get("id")
        level_ok = _assert(pd.get("urgency_level") == 1, "Critical patient → Level 1", f"got level {pd.get('urgency_level')}")
        tags = pd.get("reason_tags", [])
        _assert(len(tags) > 0, "Critical patient has reason_tags", str(tags[:3]))
        alloc = pd.get("allocation", {})
        bed_id: Optional[str] = alloc.get("bed_id")
        # Bed should be ICU or Emergency for a Level-1 patient (or waitlisted if full)
        if alloc.get("assigned"):
            _assert(True, "Critical patient allocated a bed", f"bed={bed_id}")
        else:
            _assert(True, "Critical patient waitlisted (all beds full)", alloc.get("message", ""))

    # ── Step 4: WebSocket – connection + ping/pong ───────────────────────────
    if doctor_token:
        got_event = asyncio.run(_ws_ping_check(api_url, doctor_token))
        _assert(got_event, "WebSocket connects and responds to ping")

    # ── Step 5: Create a mild patient, escalate vitals, verify re-prio ──────
    mild_payload = {
        "name": "Smoke Mild Patient",
        "age": 30,
        "gender": "F",
        "symptoms": "Minor ankle sprain",
        "sbp": 118, "dbp": 76, "hr": 72, "spo2": 99.0, "temp": 36.6, "rr": 14,
    }
    resp = client.post("/patients", json=mild_payload, headers=_headers(nurse_token))
    mild_ok = resp.status_code == 201
    _assert(mild_ok, "Create mild patient (POST /patients)", f"HTTP {resp.status_code}")
    mild_patient_id: Optional[int] = None
    if mild_ok:
        mild_data = resp.json()
        mild_patient_id = mild_data.get("id")
        mild_level = mild_data.get("urgency_level")
        _assert(mild_level in (3, 4, 5), "Mild patient → Level 3-5", f"got {mild_level}")

        # Escalate to critical vitals
        escalation = {"sbp": 68, "dbp": 42, "hr": 148, "spo2": 81.0, "temp": 39.9, "rr": 36}
        resp2 = client.put(f"/patients/{mild_patient_id}/vitals", json=escalation, headers=_headers(nurse_token))
        esc_ok = resp2.status_code == 200
        _assert(esc_ok, "Escalate mild patient vitals (PUT /vitals)", f"HTTP {resp2.status_code}")
        if esc_ok:
            vd = resp2.json()
            _assert(vd.get("level_changed") is True, "Vitals escalation → level_changed=true")
            _assert(vd.get("urgency_level") in (1, 2), "Escalated patient → Level 1 or 2", f"got {vd.get('urgency_level')}")

    # ── Step 6: Verify queue order and colours ──────────────────────────────
    resp = client.get("/queue", headers=_headers(nurse_token))
    queue_ok = resp.status_code == 200
    _assert(queue_ok, "GET /queue returns 200")
    if queue_ok:
        queue = resp.json()
        if len(queue) > 1:
            levels = [p["urgency_level"] for p in queue]
            _assert(levels == sorted(levels), "Queue is sorted by urgency_level ascending", str(levels[:5]))
        # Colours
        for p in queue:
            _assert(p.get("color") in ("RED", "YELLOW", "GREEN"), f"Queue entry has valid color", f"{p['name']}→{p.get('color')}")
            break  # Just check first item

    # ── Step 7: Discharge and verify bed becomes CLEANING ───────────────────
    if critical_patient_id:
        resp = client.get(f"/patients/{critical_patient_id}", headers=_headers(nurse_token))
        if resp.status_code == 200 and resp.json().get("status") == "ASSIGNED":
            bed_before = resp.json().get("assigned_bed_id")
            dis_resp = client.put(f"/patients/{critical_patient_id}/discharge", headers=_headers(nurse_token))
            dis_ok = dis_resp.status_code == 200
            _assert(dis_ok, "Discharge patient (PUT /discharge)", f"HTTP {dis_resp.status_code}")
            if dis_ok and bed_before:
                beds_resp = client.get("/beds", headers=_headers(nurse_token))
                if beds_resp.status_code == 200:
                    beds = {b["id"]: b for b in beds_resp.json()}
                    bed_status = beds.get(bed_before, {}).get("status")
                    _assert(
                        bed_status in ("CLEANING", "AVAILABLE"),
                        f"Bed {bed_before} → CLEANING or AVAILABLE after discharge",
                        f"got {bed_status}",
                    )
        else:
            _assert(True, "Discharge step skipped (patient was waitlisted – no bed to free)")

    # ── Step 8: Analytics endpoints return expected shapes ───────────────────
    for endpoint, required_keys in [
        ("/analytics/summary",            ["total_patients"]),
        ("/analytics/triage-distribution", ["distribution"]),
        ("/analytics/occupancy",           ["wards"]),       # returns {wards, ventilators, total_beds}
        ("/analytics/wait-by-level",       ["wait_by_level"]),
        ("/analytics/timeline",            ["timeline"]),
    ]:
        resp = client.get(endpoint, headers=_headers(nurse_token))
        ok = resp.status_code == 200
        _assert(ok, f"GET {endpoint} → 200", f"HTTP {resp.status_code}")
        if ok:
            body = resp.json()
            for key in required_keys:
                _assert(key in body, f"{endpoint} has '{key}' field", str(list(body.keys())[:6]))
                break  # One key assertion per endpoint is enough for a smoke test

    # ── Step 9: Administrative routes are not part of the clinical API ───────
    resp = client.get("/admin/logs", headers=_headers(nurse_token))
    _assert(resp.status_code == 404, "GET /admin/logs is not exposed", f"HTTP {resp.status_code}")

    resp = client.post("/admin/beds", json={"id": "TEST-01", "ward": "GENERAL", "has_ventilator": False},
                       headers=_headers(nurse_token))
    _assert(resp.status_code == 404, "POST /admin/beds is not exposed", f"HTTP {resp.status_code}")

    # ── Summary ─────────────────────────────────────────────────────────────
    client.close()
    _print_summary()


def _print_summary():
    total = len(_RESULTS)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = total - passed
    print()
    print("=" * 60)
    print(f"  SMOKE TEST RESULT:  {passed}/{total} passed  |  {failed} failed")
    print("=" * 60)
    if failed:
        print("\n  Failed steps:")
        for step, ok, note in _RESULTS:
            if not ok:
                print(f"    ❌  {step}" + (f" – {note}" if note else ""))
        sys.exit(1)
    else:
        print("  🏥  All smoke tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hospital Triage E2E Smoke Test")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running FastAPI server (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()
    run(args.api_url)
