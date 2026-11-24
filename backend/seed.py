"""
Initialize the database schema and remove only legacy demo login accounts.
No beds, doctors, nurses, shifts, or patients are fabricated by this script.
"""
from database import Base, SessionLocal, engine
from models import AdminLog, User, UserRole


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        legacy_names = ["admin", "nurse1", "nurse2", "dr1", "dr2", "dr3", "dr4", "dr5"]
        legacy_users = db.query(User).filter(
            (User.username.in_(legacy_names)) | (User.role == UserRole.ADMIN)
        ).all()
        legacy_ids = [u.id for u in legacy_users]
        if legacy_ids:
            db.query(AdminLog).filter(AdminLog.user_id.in_(legacy_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(legacy_ids)).delete(synchronize_session=False)
            db.commit()
        print("Database schema is ready.")
        print("No hospital resources or staff accounts were created.")
        print("Create a clinical staff account with: python create_staff.py")
        print("Add real hospital beds with: python create_bed.py")
        print("For an existing demo database, run: python migrate_demo_resources.py")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
