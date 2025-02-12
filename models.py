from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from database import Base  # Import Base from database.py
from enum import Enum as PyEnum

class StatusEnum(PyEnum):
    available = "available"
    unavailable = "unavailable"
    on_the_way = "on_the_way"
    completed = "completed"

# SQLAlchemy model for Hospital
class Hospital(Base):
    __tablename__ = 'hospitals'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)  # Can store as "lat,lng"

    ambulances = relationship("Ambulance", back_populates="hospital")

# SQLAlchemy model for Ambulance
class Ambulance(Base):
    __tablename__ = 'ambulances'

    id = Column(Integer, primary_key=True, index=True)
    vehicle_number = Column(String, unique=True, index=True)
    ambulance_name = Column(String, nullable=False)  # ✅ Added this field
    current_location = Column(String)  # Store as "lat,lng"
    status = Column(Enum(StatusEnum), default=StatusEnum.available)

    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    hospital = relationship("Hospital", back_populates="ambulances")

#SQLAlchemy model for Patient
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=True)   # Store latitude
    longitude = Column(Float, nullable=True)  # Store longitude