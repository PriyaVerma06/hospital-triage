"""
Simulation script for testing hospital emergency department triage and resource allocation.
Generates realistic patient cohorts with clinical vitals distributions and streams them
to the FastAPI triage API.
"""

import argparse
import random
import sys
from typing import Dict, List
import httpx

from database import SessionLocal
from models import Alert, AuditLog, Bed, BedStatus, Doctor, Patient


FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
               "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
               "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
               "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White"]


def reset_database():
    """Reset database state directly: clears patients, audit logs, and resets beds/doctors.
    Preserves User, Shift, and AdminLog records."""
    print("=" * 60)
    print("Resetting database to clean initial state (preserving users, shifts, admin logs)...")
    db = SessionLocal()
    try:
        # 1. Delete alerts, audit logs, and patient records (preserve User, Shift, AdminLog)
        db.query(Alert).delete()
        db.query(AuditLog).delete()
        db.query(Patient).delete()

        # 2. Reset all beds to AVAILABLE
        for bed in db.query(Bed).all():
            bed.status = BedStatus.AVAILABLE

        # 3. Reset all doctors to AVAILABLE with 0 active patients
        for doctor in db.query(Doctor).all():
            doctor.is_available = True
            doctor.active_patients_count = 0

        db.commit()
        print("✓ Database reset: patients/audit logs cleared, all beds & doctors available.")
        print("=" * 60)
    finally:
        db.close()


def generate_patient(index: int) -> Dict:
    """
    Generate realistic patient demographics and vitals.
    Distribution: ~10% Critical (Level 1), ~20% Serious (Level 2-3), ~70% Mild (Level 4-5).
    """
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    gender = random.choice(["M", "F"])
    tier = random.random()

    if tier < 0.10:
        # Critical Patient (~10%) -> Urgency Level 1
        age = random.randint(50, 85)
        sbp = random.choice([random.randint(65, 78), random.randint(185, 215)])
        dbp = random.choice([random.randint(40, 50), random.randint(110, 125)])
        hr = random.choice([random.randint(35, 45), random.randint(142, 165)])
        spo2 = random.randint(80, 89)
        temp = round(random.choice([random.uniform(34.2, 35.2), random.uniform(39.5, 40.8)]), 1)
        rr = random.choice([random.randint(6, 9), random.randint(31, 38)])
        symptoms = random.choice([
            "Severe crushing chest pain, unresponsive, gasping for air",
            "Acute massive blood loss, trauma, unconscious",
            "Severe respiratory distress, cyanosis, cannot breathe",
        ])
    elif tier < 0.30:
        # Serious Patient (~20%) -> Urgency Level 2 or 3
        age = random.randint(30, 75)
        sbp = random.randint(140, 168)
        dbp = random.randint(88, 102)
        hr = random.randint(102, 126)
        spo2 = random.randint(91, 94)
        temp = round(random.uniform(37.5, 38.9), 1)
        rr = random.randint(22, 28)
        symptoms = random.choice([
            "Acute substernal chest pain radiating to left shoulder",
            "Severe acute lower right abdominal pain with chills",
            "Deep laceration with significant bleeding",
            "High fever, shivering, shortness of breath",
        ])
    else:
        # Mild / Non-Urgent Patient (~70%) -> Urgency Level 4 or 5
        age = random.randint(18, 65)
        sbp = random.randint(112, 128)
        dbp = random.randint(68, 84)
        hr = random.randint(62, 88)
        spo2 = random.randint(96, 100)
        temp = round(random.uniform(36.4, 37.2), 1)
        rr = random.randint(12, 18)
        symptoms = random.choice([
            "Minor ankle sprain after twisting foot",
            "Mild headache, requests prescription refill",
            "Shallow paper cut on thumb from kitchen accident",
            "Routine checkup and physical exam",
            "Minor skin abrasion and scrape",
            "Mild seasonal allergy symptoms, feeling stable",
        ])

    return {
        "name": name,
        "age": age,
        "gender": gender,
        "symptoms": symptoms,
        "sbp": sbp,
        "dbp": dbp,
        "hr": hr,
        "spo2": float(spo2),
        "temp": temp,
        "rr": rr,
    }


def run_simulation(num_patients: int = 25, api_url: str = "http://127.0.0.1:8000"):
    """POST N generated patients to the triage API and summarize allocation results."""
    print(f"\nStarting hospital triage simulation: streaming {num_patients} patients to {api_url}...")
    print("-" * 60)

    assigned_count = 0
    waitlisted_count = 0
    level_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    with httpx.Client(base_url=api_url, timeout=10.0) as client:
        # Check API health
        try:
            health = client.get("/health")
            if health.status_code != 200:
                print(f"Error: API health check failed with status {health.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"Error connecting to API at {api_url}: {e}")
            print("Please ensure the FastAPI server is running with: uvicorn main:app --reload")
            sys.exit(1)

        # Authenticate as nurse1 to obtain Bearer token for protected endpoints
        try:
            login_resp = client.post("/auth/login", data={"username": "nurse1", "password": "demo123"})
            if login_resp.status_code != 200:
                print(f"Error logging in as nurse1: {login_resp.status_code} - {login_resp.text}")
                sys.exit(1)
            token = login_resp.json()["access_token"]
            client.headers["Authorization"] = f"Bearer {token}"
            print("✓ Authenticated as 'nurse1' with Bearer token.")
        except Exception as e:
            print(f"Authentication error connecting to {api_url}: {e}")
            sys.exit(1)

        # Ingest patients sequentially
        for i in range(1, num_patients + 1):
            patient_payload = generate_patient(i)
            resp = client.post("/patients", json=patient_payload)
            if resp.status_code != 201:
                print(f"Failed to admit patient {i}: {resp.status_code} - {resp.text}")
                continue

            data = resp.json()
            urgency = data["urgency_level"]
            level_counts[urgency] = level_counts.get(urgency, 0) + 1
            alloc = data.get("allocation", {})
            is_assigned = alloc.get("assigned", False)

            if is_assigned:
                assigned_count += 1
                status_str = f"ASSIGNED -> Bed {alloc.get('bed_id')} | Dr. {alloc.get('doctor_id')}"
            else:
                waitlisted_count += 1
                status_str = f"WAITLISTED ({alloc.get('message', 'No resources')})"

            print(f"[{i:02d}/{num_patients:02d}] {data['name']:<20} | Level {urgency} | {status_str}")

        # Retrieve and display final resource utilization summary
        summary_resp = client.get("/resources/summary")
        summary = summary_resp.json()

    print("\n" + "=" * 60)
    print("SIMULATION SUMMARY")
    print("=" * 60)
    print(f"Total Patients Admitted : {num_patients}")
    print(f"Successfully Assigned   : {assigned_count} ({assigned_count / num_patients * 100:.1f}%)")
    print(f"Waitlisted in Queue     : {waitlisted_count} ({waitlisted_count / num_patients * 100:.1f}%)")
    print("-" * 60)
    print("Triage Acuity Distribution:")
    for lvl in sorted(level_counts.keys()):
        count = level_counts[lvl]
        pct = (count / num_patients) * 100 if num_patients > 0 else 0
        print(f"  Level {lvl}: {count:2d} patients ({pct:.1f}%)")

    print("-" * 60)
    print("Final Hospital Resource Utilization:")
    print("  Ward Bed Statuses:")
    for ward, counts in summary["beds_by_ward"].items():
        print(f"    {ward:<10}: {counts['available']} Available / {counts['occupied']} Occupied / {counts['cleaning']} Cleaning (Total {counts['total']})")
    print(f"  Free Ventilators      : {summary['free_ventilators']}")
    print(f"  Available Doctors     : {summary['doctors_available']} of {summary['total_doctors']}")
    print(f"  Patients in Queue     : {summary['patients_waiting']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Hospital Triage & Resource Allocation Simulator")
    parser.add_argument("-n", "--patients", type=int, default=25, help="Number of patients to simulate (default: 25)")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000", help="API base URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--reset", action="store_true", help="Reset DB: clear patients/audit logs and free resources first")
    args = parser.parse_args()

    if args.reset:
        reset_database()

    run_simulation(num_patients=args.patients, api_url=args.api_url)


if __name__ == "__main__":
    main()
