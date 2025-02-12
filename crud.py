from sqlalchemy.orm import Session
from models import Ambulance
from schemas import AmbulanceCreate

def create_ambulance(db: Session, ambulance_data: AmbulanceCreate):
    new_ambulance = Ambulance(**ambulance_data.dict())  # Convert Pydantic model to SQLAlchemy model
    db.add(new_ambulance)
    db.commit()
    db.refresh(new_ambulance)
    return new_ambulance

def get_ambulances(db: Session):
    return db.query(Ambulance).all()

def get_ambulance_by_id(db: Session, ambulance_id: int):
    return db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
