#defines how your class that defines how your data looks like and the validation requirements it needs to pass in order to be valid
# receives data

from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

# Pydantic model for Hospital
class HospitalBase(BaseModel):
    name: str
    location: str

class HospitalCreate(HospitalBase):
    pass

class HospitalResponse(HospitalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# Pydantic model for Ambulance
class AmbulanceBase(BaseModel):
    vehicle_number: str
    current_location: str
    hospital_id: int

class StatusEnum(str, Enum):
    available = "available"
    unavailable = "unavailable"
    on_the_way = "on_the_way"
    completed = "completed"

# Pydantic schema for creating an ambulance
class AmbulanceCreate(BaseModel):
    vehicle_number: str
    ambulance_name: str  
    current_location: str
    status: StatusEnum = StatusEnum.available  # Optional, defaults to 'available'
    hospital_id: int

    model_config = ConfigDict(from_attributes=True)

# Pydantic schema for the response (display the ambulance details)
class AmbulanceResponse(BaseModel):
    id: int
    vehicle_number: str
    current_location: str
    status: StatusEnum
    hospital_id: int

    model_config = ConfigDict(from_attributes=True) 

class AmbulanceRequest(BaseModel):
    hospital_id: int
    client_location: str

    model_config = ConfigDict(from_attributes=True)

# Base model for creating a new patient
class PatientCreate(BaseModel):
    name: str
    phone_number: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# Model for updating patient location
class PatientLocationUpdate(BaseModel):
    hospital_id: int
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)

class PatientResponse(PatientCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

class LocationUpdate(BaseModel):
    lat: float
    lon: float