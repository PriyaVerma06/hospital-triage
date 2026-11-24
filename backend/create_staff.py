"""
Provision a clinical staff account from the trusted hospital server console.
There is no public signup endpoint. Only NURSE and DOCTOR accounts are supported.
"""
import getpass
import re

from auth import hash_password
from database import Base, SessionLocal, engine
from models import Doctor, DoctorSpecialty, User, UserRole


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Create authorized clinical staff account")
        username = input("Username: ").strip()
        full_name = input("Full name: ").strip()
        role_text = input("Role (NURSE/DOCTOR): ").strip().upper()

        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
            raise SystemExit("Username must be 3-40 characters (letters, numbers, ., _, -).")
        if not full_name:
            raise SystemExit("Full name is required.")
        if role_text not in {"NURSE", "DOCTOR"}:
            raise SystemExit("Only NURSE and DOCTOR accounts can be created.")
        if db.query(User).filter(User.username == username).first():
            raise SystemExit("That username already exists.")

        doctor_id = None
        if role_text == "DOCTOR":
            choices = list(DoctorSpecialty)
            print("Select medical specialty:")
            for index, specialty in enumerate(choices, start=1):
                print(f"  {index}: {specialty.value}")
            raw_choice = input("Specialty number: ").strip()
            if not raw_choice.isdigit() or not 1 <= int(raw_choice) <= len(choices):
                raise SystemExit("Select a valid specialty number.")
            specialty = choices[int(raw_choice) - 1]
            doctor = Doctor(
                name=full_name,
                specialty=specialty,
                is_available=True,
                active_patients_count=0,
            )
            db.add(doctor)
            db.flush()
            doctor_id = doctor.id

        password = getpass.getpass("Password (minimum 12 characters): ")
        confirm = getpass.getpass("Confirm password: ")
        if len(password) < 12:
            raise SystemExit("Password must be at least 12 characters.")
        if password != confirm:
            raise SystemExit("Passwords do not match.")

        user = User(
            username=username,
            full_name=full_name,
            role=UserRole(role_text),
            doctor_id=doctor_id,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {role_text} account '{username}'.")
        if doctor_id is not None:
            print(f"Created and linked doctor record #{doctor_id} for {full_name}.")
        print("Password was neither displayed nor stored in plaintext.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
