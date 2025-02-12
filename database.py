from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL (Using SQLite for simplicity)
DATABASE_URL = "sqlite:///./hospital.db"

# Create Engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Session Local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base Class for Models
Base = declarative_base()

# Dependency to Get Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
