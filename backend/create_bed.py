"""
Add a real hospital bed from the trusted backend/server console.
Run from backend/: python create_bed.py
"""
from database import Base, SessionLocal, engine
from models import Bed, BedStatus, BedWard


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bed_id = input("Bed ID (e.g. ICU-A01): ").strip().upper()
        if not bed_id or len(bed_id) > 20:
            raise SystemExit("Enter a bed ID between 1 and 20 characters.")
        if db.query(Bed).filter(Bed.id == bed_id).first():
            raise SystemExit("That bed ID already exists.")

        wards = list(BedWard)
        print("Ward:")
        for index, ward in enumerate(wards, start=1):
            print(f"  {index}: {ward.value}")
        raw = input("Ward number: ").strip()
        if not raw.isdigit() or not 1 <= int(raw) <= len(wards):
            raise SystemExit("Select a valid ward.")
        ward = wards[int(raw) - 1]

        raw_vent = input("Has ventilator? (y/n): ").strip().lower()
        if raw_vent not in {"y", "n"}:
            raise SystemExit("Enter y or n.")
        bed = Bed(
            id=bed_id,
            ward=ward,
            has_ventilator=(raw_vent == "y"),
            status=BedStatus.AVAILABLE,
        )
        db.add(bed)
        db.commit()
        print(f"Added bed {bed_id} ({ward.value}); status is AVAILABLE.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
