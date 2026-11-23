"""
Database configuration and session management for the hospital triage system.
Uses SQLite as the local database engine.
"""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Locate the SQLite database file in the backend directory
BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'triage.db'}"

# Engine with check_same_thread disabled for multi-threaded FastAPI compatibility
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base for SQLAlchemy models
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a transactional DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
