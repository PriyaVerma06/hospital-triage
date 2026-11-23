"""
Seed script to populate initial beds, on-duty doctors, and RBAC users in triage.db.
Idempotent: clears existing Bed, Doctor, and User records so it can be safely re-run.
"""

from auth import hash_password
from database import Base, SessionLocal, engine
from models import Alert, Bed, BedStatus, BedWard, Doctor, DoctorSpecialty, User, UserRole


def seed():
    # Ensure tables are created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Clear existing rows for idempotency
        # Clear users and alerts first to respect foreign keys
        db.query(Alert).delete()
        db.query(User).delete()
        db.query(Bed).delete()
        db.query(Doctor).delete()
        db.commit()

        # 1. Seed 15 beds: 4 ICU (with ventilators), 5 EMERGENCY, 6 GENERAL
        beds = [
            *(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE) for i in range(1, 5)),
            *(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 6)),
            *(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 7)),
        ]

        # 2. Seed 5 on-duty doctors: 2 Emergency, 1 Cardiology, 2 General
        doctors = [
            Doctor(name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
        ]

        db.add_all(beds + doctors)
        db.flush()  # Assign doctor IDs

        # 3. Seed Users with password "demo123"
        default_pw_hash = hash_password("demo123")
        users = [
            User(
                username="admin",
                password_hash=default_pw_hash,
                full_name="System Administrator",
                role=UserRole.ADMIN,
                doctor_id=None,
                is_active=True,
            ),
            User(
                username="nurse1",
                password_hash=default_pw_hash,
                full_name="Nurse Sarah Jenkins",
                role=UserRole.NURSE,
                doctor_id=None,
                is_active=True,
            ),
            User(
                username="nurse2",
                password_hash=default_pw_hash,
                full_name="Nurse David Kim",
                role=UserRole.NURSE,
                doctor_id=None,
                is_active=True,
            ),
        ]

        # One DOCTOR user per seeded doctor named dr1..dr5
        for idx, doc in enumerate(doctors, start=1):
            users.append(
                User(
                    username=f"dr{idx}",
                    password_hash=default_pw_hash,
                    full_name=doc.name,
                    role=UserRole.DOCTOR,
                    doctor_id=doc.id,
                    is_active=True,
                )
            )

        db.add_all(users)
        db.commit()

        print(f"Seeded {len(beds)} beds and {len(doctors)} doctors successfully.")
        print(f"Seeded {len(users)} user accounts (password: 'demo123'):")
        for u in users:
            doc_str = f" [Linked to Doctor #{u.doctor_id}]" if u.doctor_id else ""
            print(f"  - {u.username:<8} ({u.role.value:<6}) : {u.full_name}{doc_str}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
