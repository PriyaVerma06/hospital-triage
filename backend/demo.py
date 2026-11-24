"""
demo.py – Demo data tooling for the hospital triage system.

Subcommands
-----------
  python demo.py reset      Rebuild the database from scratch (drop + seed),
                            leaving the hospital empty of patients.
  python demo.py scenario   Run a scripted, repeatable story against the
                            running API (requires the server to be up).

Usage
-----
  cd backend/
  python demo.py reset
  python demo.py scenario
  python demo.py scenario --speed fast
"""

import argparse
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Fixed patient roster (deterministic vitals so every run is identical)
# ---------------------------------------------------------------------------

# 6 mild/serious patients (Levels 3-5 expected)
MILD_SERIOUS = [
    {
        "name": "Emily Parker", "age": 34, "gender": "F",
        "symptoms": "Minor ankle sprain after twisting foot",
        "sbp": 118, "dbp": 76, "hr": 72, "spo2": 99.0, "temp": 36.6, "rr": 14,
    },
    {
        "name": "Carlos Rivera", "age": 28, "gender": "M",
        "symptoms": "Mild headache, requests prescription refill",
        "sbp": 122, "dbp": 80, "hr": 68, "spo2": 98.0, "temp": 36.8, "rr": 15,
    },
    {
        "name": "Patricia Moore", "age": 55, "gender": "F",
        "symptoms": "High fever, shivering, shortness of breath",
        "sbp": 148, "dbp": 94, "hr": 110, "spo2": 93.0, "temp": 38.7, "rr": 24,
    },
    {
        "name": "David Kim", "age": 42, "gender": "M",
        "symptoms": "Acute substernal chest pain radiating to left shoulder",
        "sbp": 155, "dbp": 96, "hr": 115, "spo2": 92.0, "temp": 37.8, "rr": 26,
    },
    {
        "name": "Sandra White", "age": 19, "gender": "F",
        "symptoms": "Mild seasonal allergy symptoms, feeling stable",
        "sbp": 115, "dbp": 72, "hr": 65, "spo2": 99.0, "temp": 36.5, "rr": 13,
    },
    {
        "name": "Michael Torres", "age": 60, "gender": "M",
        "symptoms": "Severe acute lower right abdominal pain with chills",
        "sbp": 162, "dbp": 100, "hr": 118, "spo2": 92.0, "temp": 38.5, "rr": 25,
    },
]

# 3 critical patients (Level 1 expected; ICU beds + ventilators + alerts)
CRITICAL_BATCH_1 = [
    {
        "name": "Margaret Chen", "age": 72, "gender": "F",
        "symptoms": "Severe crushing chest pain, unresponsive, gasping for air",
        "sbp": 70, "dbp": 44, "hr": 38, "spo2": 83.0, "temp": 35.0, "rr": 7,
    },
    {
        "name": "Robert Hayes", "age": 68, "gender": "M",
        "symptoms": "Acute massive blood loss, trauma, unconscious",
        "sbp": 68, "dbp": 42, "hr": 155, "spo2": 81.0, "temp": 34.8, "rr": 8,
    },
    {
        "name": "Barbara Lewis", "age": 65, "gender": "F",
        "symptoms": "Severe respiratory distress, cyanosis, cannot breathe",
        "sbp": 195, "dbp": 118, "hr": 148, "spo2": 82.0, "temp": 39.8, "rr": 34,
    },
]

# 2 more critical patients to overflow ICU
CRITICAL_BATCH_2 = [
    {
        "name": "James Anderson", "age": 78, "gender": "M",
        "symptoms": "Severe crushing chest pain, unresponsive, gasping for air",
        "sbp": 72, "dbp": 46, "hr": 42, "spo2": 80.0, "temp": 34.5, "rr": 6,
    },
    {
        "name": "Linda Thompson", "age": 59, "gender": "F",
        "symptoms": "Acute massive blood loss, trauma, unconscious",
        "sbp": 65, "dbp": 40, "hr": 160, "spo2": 79.0, "temp": 35.1, "rr": 35,
    },
]

# Escalated vitals for Emily Parker (scene d) – from mild to critical
ESCALATION_VITALS = {
    "sbp": 68, "dbp": 42, "hr": 148, "spo2": 81.0, "temp": 39.9, "rr": 36,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_API = "http://127.0.0.1:8000"


def _pause(seconds: float, speed: str):
    """Sleep for a demo-paced interval, shortened when speed=='fast'."""
    factor = {"normal": 1.0, "fast": 0.1}.get(speed, 1.0)
    time.sleep(seconds * factor)


def _narrate(msg: str):
    """Print a clearly formatted narration line."""
    print(f"\n  🎬  {msg}")


def _ok(msg: str):
    print(f"      ✅  {msg}")


def _warn(msg: str):
    print(f"      ⚠️   {msg}")


def _admit(client: httpx.Client, payload: dict, label: str) -> dict:
    """POST /patients and print a one-liner result."""
    resp = client.post("/patients", json=payload)
    if resp.status_code != 201:
        _warn(f"Admission failed for {label}: {resp.status_code} – {resp.text[:120]}")
        return {}
    data = resp.json()
    alloc = data.get("allocation", {})
    bed = alloc.get("bed_id", "—")
    dr = alloc.get("doctor_id", "—")
    assigned = alloc.get("assigned", False)
    status_str = f"Level {data['urgency_level']} | {'ASSIGNED → ' + str(bed) + ' / Dr.' + str(dr) if assigned else 'WAITLISTED – ' + alloc.get('message', '')}"
    print(f"      • {data['name']:<22}  {status_str}")
    return data


# ---------------------------------------------------------------------------
# Subcommand: reset
# ---------------------------------------------------------------------------

def cmd_reset():
    """
    Drop and recreate all tables via SQLAlchemy, then run the seed script
    to populate beds, doctors, users, and today's shifts.
    The hospital is left empty of patients.
    """
    print("=" * 60)
    print("  DEMO RESET – rebuilding database from scratch")
    print("=" * 60)

    # Import here so the script can be run from backend/ directory
    try:
        from database import Base, engine
        from seed import seed
    except ImportError as exc:
        print(f"Import error (run from backend/ directory): {exc}")
        sys.exit(1)

    print("  Dropping all tables …")
    Base.metadata.drop_all(bind=engine)
    print("  Creating all tables …")
    Base.metadata.create_all(bind=engine)
    print("  Seeding beds, doctors, users, shifts …")
    seed()

    print()
    print("  ✅  Database rebuilt. Hospital is clean and ready.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Subcommand: scenario
# ---------------------------------------------------------------------------

def cmd_scenario(speed: str = "normal", api_url: str = _DEFAULT_API):
    """
    Run a fixed, scripted patient scenario against the running API.
    Every step is narrated so the audience can follow along.
    """
    print("=" * 60)
    print("  DEMO SCENARIO – scripted hospital triage story")
    print(f"  API: {api_url}  |  speed: {speed}")
    print("=" * 60)

    # -- Connect & authenticate ------------------------------------------------
    try:
        with httpx.Client(base_url=api_url, timeout=15.0) as client:
            health = client.get("/health")
            if health.status_code != 200:
                print(f"  ❌  Health check failed ({health.status_code}). Is the server running?")
                sys.exit(1)
    except Exception as exc:
        print(f"  ❌  Cannot reach {api_url}: {exc}")
        print("  Run: cd backend && uvicorn main:app --reload")
        sys.exit(1)

    nurse_token = _login(api_url, "nurse1", "demo123")
    admin_token = _login(api_url, "admin", "demo123")

    summary = {"assigned": 0, "waitlisted": 0, "escalated": False, "discharged": False}

    with httpx.Client(base_url=api_url, timeout=15.0) as client:
        client.headers["Authorization"] = f"Bearer {nurse_token}"

        # ------------------------------------------------------------------ a
        _narrate("SCENE A – Admitting 6 mild/serious patients (filling General & Emergency wards partly)")
        _pause(0.5, speed)
        for p in MILD_SERIOUS:
            data = _admit(client, p, p["name"])
            if data:
                if data.get("allocation", {}).get("assigned"):
                    summary["assigned"] += 1
                else:
                    summary["waitlisted"] += 1
            _pause(0.4, speed)

        _pause(1.0, speed)

        # ------------------------------------------------------------------ b
        _narrate("SCENE B – Admitting 3 CRITICAL patients → ICU beds + ventilators + alert dispatch")
        _pause(0.5, speed)
        critical_ids = []
        for p in CRITICAL_BATCH_1:
            data = _admit(client, p, p["name"])
            if data:
                critical_ids.append(data["id"])
                if data.get("allocation", {}).get("assigned"):
                    summary["assigned"] += 1
                else:
                    summary["waitlisted"] += 1
            _pause(0.6, speed)

        # Print alert count
        _pause(0.3, speed)
        try:
            alerts_resp = client.get("/alerts")
            if alerts_resp.status_code == 200:
                n = len(alerts_resp.json())
                _ok(f"{n} alert(s) dispatched so far")
        except Exception:
            pass

        _pause(1.0, speed)

        # ------------------------------------------------------------------ c
        _narrate("SCENE C – 2 more CRITICAL patients when ICU may be full → fallback to Emergency / WAITLISTED")
        _pause(0.5, speed)
        overflow_patient_id = None
        for p in CRITICAL_BATCH_2:
            data = _admit(client, p, p["name"])
            if data:
                if not data.get("allocation", {}).get("assigned"):
                    summary["waitlisted"] += 1
                    overflow_patient_id = data["id"]
                    _ok(f"'{data['name']}' waitlisted (NO BED available for Level 1)")
                else:
                    summary["assigned"] += 1
                    _ok(f"'{data['name']}' placed in Emergency/General fallback bed")
            _pause(0.6, speed)

        _pause(1.0, speed)

        # ------------------------------------------------------------------ d
        _narrate("SCENE D – Emily Parker (mild ankle sprain) deteriorates → vitals go critical → re-prioritization!")
        _pause(0.5, speed)

        # Find Emily Parker by name
        patients_resp = client.get("/patients", params={"search": "Emily Parker"})
        emily_id = None
        if patients_resp.status_code == 200 and patients_resp.json():
            emily_id = patients_resp.json()[0]["id"]

        if emily_id:
            prev_resp = client.get(f"/patients/{emily_id}")
            prev_level = prev_resp.json().get("urgency_level", "?") if prev_resp.status_code == 200 else "?"
            vitals_resp = client.put(f"/patients/{emily_id}/vitals", json=ESCALATION_VITALS)
            if vitals_resp.status_code == 200:
                vd = vitals_resp.json()
                new_level = vd.get("urgency_level")
                changed = vd.get("level_changed", False)
                if changed:
                    summary["escalated"] = True
                    _ok(f"Emily Parker: Level {prev_level} → Level {new_level} (escalation alert dispatched!)")
                else:
                    _ok(f"Emily Parker: vitals updated, still Level {new_level}")
            else:
                _warn(f"Vitals update failed: {vitals_resp.status_code}")
        else:
            _warn("Could not find Emily Parker in DB – skipping escalation scene")

        _pause(1.0, speed)

        # ------------------------------------------------------------------ e
        _narrate("SCENE E – Discharging an ICU patient + marking bed AVAILABLE as admin → auto-assign from queue")
        _pause(0.5, speed)

        # Pick the first assigned critical patient we admitted
        discharged = False
        for cid in critical_ids:
            p_resp = client.get(f"/patients/{cid}")
            if p_resp.status_code == 200:
                p_data = p_resp.json()
                if p_data.get("status") == "ASSIGNED":
                    dis_resp = client.put(f"/patients/{cid}/discharge")
                    if dis_resp.status_code == 200:
                        freed_bed = p_data.get("assigned_bed_id")
                        _ok(f"Discharged '{p_data['name']}' (was in bed {freed_bed})")
                        discharged = True
                        summary["discharged"] = True

                        # Admin: set the freed bed to AVAILABLE to trigger auto-assign
                        if freed_bed:
                            client.headers["Authorization"] = f"Bearer {admin_token}"
                            bed_resp = client.put(
                                f"/beds/{freed_bed}/status",
                                json={"status": "AVAILABLE"},
                            )
                            if bed_resp.status_code == 200:
                                _ok(f"Bed {freed_bed} marked AVAILABLE → allocation engine runs")
                            client.headers["Authorization"] = f"Bearer {nurse_token}"
                        break
            if discharged:
                break

        if not discharged:
            _warn("No dischargeable ASSIGNED critical patient found (scene skipped)")

        _pause(1.0, speed)

        # ------------------------------------------------------------------ f
        _narrate("SCENE F – Final summary")
        _pause(0.3, speed)

        # Pull live stats
        try:
            summary_resp = client.get("/resources/summary")
            queue_resp = client.get("/queue")
            if summary_resp.status_code == 200 and queue_resp.status_code == 200:
                s = summary_resp.json()
                q = queue_resp.json()
                print()
                print("  " + "─" * 56)
                print("  SCENARIO RESULTS")
                print("  " + "─" * 56)
                print(f"  Patients assigned in scenario : {summary['assigned']}")
                print(f"  Patients waitlisted           : {summary['waitlisted']}")
                print(f"  Escalation triggered          : {'Yes ✅' if summary['escalated'] else 'No'}")
                print(f"  Discharge + auto-assign       : {'Yes ✅' if summary['discharged'] else 'No'}")
                print()
                print(f"  Current queue depth           : {len(q)} patients waiting")
                print(f"  Free ventilators              : {s.get('free_ventilators', '?')}")
                print(f"  Available doctors             : {s.get('doctors_available', '?')} / {s.get('total_doctors', '?')}")
                print("  " + "─" * 56)
        except Exception as exc:
            _warn(f"Could not fetch live summary: {exc}")

    print()
    print("  ✅  Scenario complete. Open http://localhost:5173 to see the live dashboard.")
    print("=" * 60)


def _login(api_url: str, username: str, password: str) -> str:
    """Log in and return the access token, or exit on failure."""
    with httpx.Client(base_url=api_url, timeout=10.0) as client:
        resp = client.post("/auth/login", data={"username": username, "password": password})
    if resp.status_code != 200:
        print(f"  ❌  Login failed for '{username}': {resp.status_code} – {resp.text[:120]}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"  ✓  Logged in as '{username}'")
    return token


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Hospital Triage System – demo tooling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python demo.py reset\n"
            "  python demo.py scenario\n"
            "  python demo.py scenario --speed fast\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # reset subcommand
    sub.add_parser("reset", help="Drop + recreate DB tables and seed initial data")

    # scenario subcommand
    sc = sub.add_parser("scenario", help="Run scripted patient scenario against the running API")
    sc.add_argument(
        "--speed",
        choices=["normal", "fast"],
        default="normal",
        help="Pause duration between steps (default: normal)",
    )
    sc.add_argument(
        "--api-url",
        default=_DEFAULT_API,
        help=f"API base URL (default: {_DEFAULT_API})",
    )

    args = parser.parse_args()

    if args.command == "reset":
        cmd_reset()
    elif args.command == "scenario":
        cmd_scenario(speed=args.speed, api_url=args.api_url)


if __name__ == "__main__":
    main()
