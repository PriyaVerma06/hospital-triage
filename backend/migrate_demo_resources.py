"""
One-time cleanup for databases created by the original demo seed.
Preserves patient history and any resource with live references.
Run from backend/: python migrate_demo_resources.py
"""
from database import SessionLocal
from models import Alert, Bed, Doctor, Patient, Shift, User, UserRole

DEMO_DOCTOR_NAMES = {
    "Dr. Sarah Chen", "Dr. Marcus Vance", "Dr. Elena Rostova",
    "Dr. James Wilson", "Dr. Priya Patel",
}
DEMO_BED_IDS = {
    *(f"ICU-0{i}" for i in range(1, 5)),
    *(f"ER-0{i}" for i in range(1, 6)),
    *(f"GEN-0{i}" for i in range(1, 7)),
}


def main():
    db = SessionLocal()
    try:
        # If a staff account's display name differs from the linked demo doctor,
        # create a matching doctor record and relink the account. Keep the old
        # doctor record until all clinical references are safely checked.
        doctor_users = db.query(User).filter(User.role == UserRole.DOCTOR).all()
        for user in doctor_users:
            linked = db.query(Doctor).filter(Doctor.id == user.doctor_id).first() if user.doctor_id else None
            if linked and linked.name.strip().casefold() != user.full_name.strip().casefold():
                has_patient_work = db.query(Patient).filter(Patient.assigned_doctor_id == linked.id).first()
                has_alert_work = db.query(Alert).filter(Alert.doctor_id == linked.id).first()
                if has_patient_work or has_alert_work:
                    print(
                        f"Kept {user.username} linked to doctor record {linked.id}; "
                        "existing patient/alert references require manual review."
                    )
                    continue
                replacement = Doctor(
                    name=user.full_name,
                    specialty=linked.specialty,
                    is_available=linked.is_available,
                    active_patients_count=0,
                )
                db.add(replacement)
                db.flush()
                user.doctor_id = replacement.id
                print(f"Relinked {user.username} to a new doctor record for {user.full_name}.")

        db.commit()

        removed_doctors = 0
        for doctor in db.query(Doctor).filter(Doctor.name.in_(DEMO_DOCTOR_NAMES)).all():
            has_patients = db.query(Patient).filter(Patient.assigned_doctor_id == doctor.id).first()
            has_alerts = db.query(Alert).filter(Alert.doctor_id == doctor.id).first()
            has_users = db.query(User).filter(User.doctor_id == doctor.id).first()
            if has_patients or has_alerts or has_users:
                print(f"Kept doctor {doctor.name} (ID {doctor.id}) because clinical records still reference it.")
                continue
            db.query(Shift).filter(Shift.doctor_id == doctor.id).delete(synchronize_session=False)
            db.delete(doctor)
            removed_doctors += 1

        removed_beds = 0
        for bed in db.query(Bed).filter(Bed.id.in_(DEMO_BED_IDS)).all():
            if db.query(Patient).filter(Patient.assigned_bed_id == bed.id).first():
                print(f"Kept bed {bed.id} because patient history references it.")
                continue
            db.delete(bed)
            removed_beds += 1

        db.commit()
        print(f"Migration complete. Removed {removed_doctors} unused demo doctor records and {removed_beds} unused demo beds.")
        print("Patient records and referenced hospital resources were preserved.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
