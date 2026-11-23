"""
Seed script to populate initial beds and on-duty doctors in triage.db.
Idempotent: clears existing Bed and Doctor records so it can be safely re-run.
"""

from database import Base, SessionLocal, engine
from models import Bed, BedStatus, BedWard, Doctor, DoctorSpecialty


def seed():
    # Ensure tables are created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Clear existing rows for idempotency
        db.query(Bed).delete()
        db.query(Doctor).delete()
        db.commit()

        # Seed 15 beds: 4 ICU (with ventilators), 5 EMERGENCY, 6 GENERAL
        beds = [
            *(Bed(id=f"ICU-0{i}", ward=BedWard.ICU, has_ventilator=True, status=BedStatus.AVAILABLE) for i in range(1, 5)),
            *(Bed(id=f"ER-0{i}", ward=BedWard.EMERGENCY, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 6)),
            *(Bed(id=f"GEN-0{i}", ward=BedWard.GENERAL, has_ventilator=False, status=BedStatus.AVAILABLE) for i in range(1, 7)),
        ]

        # Seed 5 on-duty doctors: 2 Emergency, 1 Cardiology, 2 General
        doctors = [
            Doctor(name="Dr. Sarah Chen", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Marcus Vance", specialty=DoctorSpecialty.EMERGENCY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Elena Rostova", specialty=DoctorSpecialty.CARDIOLOGY, is_available=True, active_patients_count=0),
            Doctor(name="Dr. James Wilson", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
            Doctor(name="Dr. Priya Patel", specialty=DoctorSpecialty.GENERAL, is_available=True, active_patients_count=0),
        ]

        db.add_all(beds + doctors)
        db.commit()
        print(f"Seeded {len(beds)} beds and {len(doctors)} doctors successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
